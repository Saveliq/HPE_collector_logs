import re

from search import SYSTEM, CHASSIS, Resources, _dict, _list, _first, _scaled, _installed, is_absent, stripJSON


def _controllers(resources):
    result = []
    for storage in resources.matching(re.escape(SYSTEM) + r"/Storage/[^/]+"):
        if is_absent(storage):
            continue
        storage_path = storage.get("@odata.id", "").rstrip("/")
        # New iDRAC: Controllers/<id>; old iDRAC: embedded StorageControllers.
        nodes = resources.matching(re.escape(storage_path) + r"/Controllers/[^/]+") if storage_path else []
        if not nodes:
            collection = resources.resolve(storage.get("Controllers"))
            nodes = [resources.resolve(ref) for ref in _list(collection.get("Members"))]
        if not nodes:
            nodes = _list(storage.get("StorageControllers"))
        oem = resources.oem(storage, "DellController")
        for node in _installed(resources, nodes, enrich_pcie=True):
            own_oem = resources.oem(node, "DellController") or oem
            node["CacheMemorySizeMiB"] = _first(
                _dict(node.get("CacheSummary")).get("TotalCacheSizeMiB"), own_oem.get("CacheSizeInMB"))
            node["CurrentOperatingMode"] = own_oem.get("CurrentControllerMode")
            node["FirmwareVersion"] = _first(node.get("FirmwareVersion"), own_oem.get("ControllerFirmwareVersion"))
            result.append(node)
    return result


def _disk_part_number(resources, disk):
    """Dell can put the serialized PPID in the standard PartNumber field."""
    oem = resources.oem(disk, "DellPhysicalDisk")
    ppid = str(oem.get("PPID") or disk.get("PPID") or "").strip().upper().replace("-", "")
    for value in (disk.get("PartNumber"), oem.get("PartNumber")):
        part = str(value or "").strip()
        if part.lower() in {"", "unknown", "n/a", "none", "null"}:
            continue
        compact = part.upper().replace("-", "")
        # Match both supplied PPID forms: TH-06DWVP-HGT00-85M-4316-A00
        # and TW0919J9ITT0081302D4A00 (older iDRAC has no OEM PPID field).
        if compact == ppid or re.fullmatch(r"[A-Z]{2}0[A-Z0-9]{17}[A-Z][0-9]{2}", compact):
            continue
        return part
    return disk.get("Model")


def get_array_controllers(json_data):
    resources = Resources(json_data)
    controllers = _controllers(resources)
    disks = _installed(resources, resources.matching(
        re.escape(SYSTEM) + r"/Storage/(?:[^/]+/)?Drives/[^/]+"))
    for disk in disks:
        disk.update(PartNumber=_disk_part_number(resources, disk),
                    CapacityGB=_scaled(disk.get("CapacityBytes"), 1 / 1e9),
                    InterfaceType=disk.get("Protocol"),
                    InterfaceSpeedMbps=_scaled(disk.get("NegotiatedSpeedGbs"), 1000),
                    FirmwareVersion=_first(disk.get("FirmwareVersion"), disk.get("Revision")))
    return stripJSON(controllers), stripJSON(disks)


def get_storage_enclosures(json_data):
    resources = Resources(json_data)
    enclosures = _installed(resources, resources.matching(r"/redfish/v1/Chassis/Enclosure\.[^/]+"))
    for enclosure in enclosures:
        location = _dict(_dict(enclosure.get("Location")).get("PartLocation"))
        description = " ".join(str(enclosure.get(field) or "") for field in ("Name", "Model", "Description"))
        if (str(location.get("LocationType", "")).lower() == "backplane" or
                "backplane" in description.lower()):
            enclosure["ComponentName"] = "Дисковая корзина (backplane)"
    return stripJSON(enclosures)


