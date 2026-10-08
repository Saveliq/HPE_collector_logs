import re

from search import SYSTEM, Resources, _dict, _list, _first, _scaled, _installed, is_absent, stripJSON


INVALID_PART_NUMBERS = {"", "unknown", "n/a", "na", "none", "null", "not available", "notavailable"}


def _controller_component_name(node, oem=None):
    """Classify a storage controller without calling every controller RAID."""
    oem = oem or {}
    label = " ".join(str(value or "") for value in (
        node.get("Id"), node.get("Name"), node.get("Model"),
        oem.get("DeviceDescription"), oem.get("ControllerMode"), oem.get("CurrentControllerMode"),
    )).lower()
    if "boss" in label or "boot optimized" in label or "boot controller" in label:
        return "Загрузочный контроллер"
    if "perc" in label or " raid" in f" {label}" or label.startswith("raid"):
        return "RAID контроллер"
    if "hba" in label or "nonraid" in label or "non-raid" in label:
        return "HBA контроллер"
    if "ahci" in label or "sata controller" in label or "ssata controller" in label:
        return "SATA/AHCI контроллер"
    return "Контроллер хранения"


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
            if len(nodes) == 1:
                node["SourceAliases"].append(storage_path)
            for index, legacy in enumerate(_list(storage.get("StorageControllers"))):
                if len(nodes) == 1 or legacy.get("MemberId") == node.get("Id"):
                    node["SourceAliases"].append(f"{storage_path}#/StorageControllers/{index}")
                    if legacy.get("@odata.id"):
                        node["SourceAliases"].append(legacy["@odata.id"])
            own_oem = resources.oem(node, "DellController") or oem
            node["CacheMemorySizeMiB"] = _first(
                _dict(node.get("CacheSummary")).get("TotalCacheSizeMiB"), own_oem.get("CacheSizeInMB"))
            node["CurrentOperatingMode"] = own_oem.get("CurrentControllerMode")
            node["FirmwareVersion"] = _first(node.get("FirmwareVersion"), own_oem.get("ControllerFirmwareVersion"))
            node["ComponentName"] = _controller_component_name(node, own_oem)
            result.append(node)
    return result


def _disk_part_number(resources, disk):
    """Return a real disk P/N; fall back to model when iDRAC has no P/N.

    Dell can put a serialized PPID in the standard PartNumber field.  Such a
    value is instance-specific and unsuitable for P/N grouping, so it is
    rejected just like the explicit 'Not Available' sentinel.
    """
    oem = resources.oem(disk, "DellPhysicalDisk")
    ppid = str(oem.get("PPID") or disk.get("PPID") or "").strip().upper().replace("-", "")
    for value in (disk.get("PartNumber"), oem.get("PartNumber")):
        part = str(value or "").strip()
        if part.lower() in INVALID_PART_NUMBERS:
            continue
        compact = part.upper().replace("-", "")
        # Match both supplied PPID forms: TH-06DWVP-HGT00-85M-4316-A00
        # and TW0919J9ITT0081302D4A00 (older iDRAC has no OEM PPID field).
        if compact == ppid or re.fullmatch(r"[A-Z]{2}0[A-Z0-9]{17}[A-Z][0-9]{2}", compact):
            continue
        return part
    model = str(disk.get("Model") or "").strip()
    return model if model.lower() not in INVALID_PART_NUMBERS else None


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
