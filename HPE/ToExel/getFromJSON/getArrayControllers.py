import re

from search import search_one, stripJSON, is_absent
from getFromJSON.getDiagnostics import component_fields

Disks = []
def get_array_controllers(json_data):
    global Disks
    Disks = []
    def sub_UnconfiguredDrives(data, id_primary_node):
        pass
    def sub_LogicalDrives(data, id_primary_node):
        node_result = {}
        node_result["CapacityMiB"] = search_one(data, r"CapacityMiB")
        node_result["Raid"] = search_one(data, r"Raid")
        node_result["Health"] = search_one(data, r"Health", path_pattern="Status")
        node_result["State"] = search_one(data, r"State", path_pattern="Status")
        return node_result
    def sub_DiskDrives(data, id_primary_node):
        node_result = {}
        node_result["BlockSizeBytes"] = search_one(data, r"BlockSizeBytes")
        node_result["CapacityGB"] = search_one(data, r"CapacityGB")
        if node_result["CapacityGB"] is None and isinstance(data.get("CapacityBytes"), (int, float)):
            node_result["CapacityGB"] = data["CapacityBytes"] / 10**9
        node_result["DiskDriveStatusReasons"] = search_one(data, r"DiskDriveStatusReasons")
        node_result["InterfaceType"] = search_one(data, r"InterfaceType")
        if node_result["InterfaceType"] is None:
            node_result["InterfaceType"] = data.get("Protocol")
        node_result["FirmwareVersion"] = search_one(data, r"VersionString", path_pattern="FirmwareVersion")
        node_result["InterfaceSpeedMbps"] = search_one(data, r"InterfaceSpeedMbps")
        if node_result["InterfaceSpeedMbps"] is None and isinstance(data.get("NegotiatedSpeedGbs"), (int, float)):
            node_result["InterfaceSpeedMbps"] = data["NegotiatedSpeedGbs"] * 1000
        node_result["MediaType"] = search_one(data, r"MediaType")
        node_result["Model"] = search_one(data, r"Model")
        node_result["PartNumber"] = data.get("PartNumber")
        node_result["Health"] = search_one(data, r"Health", path_pattern="Status")
        node_result["State"] = search_one(data, r"State", path_pattern="Status")
        node_result["SerialNumber"] = data.get("SerialNumber")
        node_result.update(component_fields(data))
        if not node_result["FirmwareVersion"]:
            node_result["FirmwareVersion"] = data.get("Revision")
        return node_result
    def _get(data, id_node):
        global Disks
        node_result = {}
        node_result["AdapterType"] = search_one(data, r"AdapterType")
        node_result["LocationFormat"] = search_one(data, r"LocationFormat")
        node_result["BackupPowerSourceStatus"] = search_one(data, r"BackupPowerSourceStatus")
        node_result["CacheMemorySizeMiB"] = search_one(data, r"CacheMemorySizeMiB")
        node_result["CurrentOperatingMode"] = search_one(data, r"CurrentOperatingMode")
        node_result["FirmwareVersion"] = search_one(data, r"VersionString", path_pattern=r"FirmwareVersion")
        node_result["Location"] = search_one(data, r"Location")
        node_result["Model"] = search_one(data, r"Model")
        node_result["PartNumber"] = data.get("ControllerPartNumber") or data.get("PartNumber")
        node_result["SerialNumber"] = data.get("SerialNumber")
        node_result["State"] = search_one(data, r"State", path_pattern=r"Status")
        node_result["Health"] = search_one(data, r"Health", path_pattern=r"Status")
        node_result.update(component_fields(data))
        disk_drives = match_by_pattern(json_data, rf"{re.escape(id_node)}/DiskDrives/[^/#]+$", "Disk", func=sub_DiskDrives)
        node_result["DiskDrives"] = disk_drives
        Disks += disk_drives
        unconfigdisk_drives = match_by_pattern(json_data, rf"{re.escape(id_node)}/UnconfiguredDrives/[^/#]+$", "Disk",
                                       func=sub_DiskDrives)
        node_result["DiskDrives"] += unconfigdisk_drives
        Disks += unconfigdisk_drives
        disk_logical_drives = match_by_pattern(json_data, rf"{re.escape(id_node)}/LogicalDrives/[^/#]+$", "Logical_Disk",
                                       func=sub_LogicalDrives)
        node_result["LogicalDiskDrives"] = disk_logical_drives
        return node_result

    def match_by_pattern(data, pattern, descr="UNDEF", func=None):
        result = []
        pattern = re.compile(pattern)
        nodes = {
            key: val for key, val in data.items()
            if pattern.match(key) and isinstance(val, dict) and not is_absent(val)
        }
        ind = 0
        for key, _data in nodes.items():
            result.append(func(_data, key))
        return result


    controllers = match_by_pattern(json_data, r".*/(ArrayControllers|HostBusAdapters)/[^/#]+$", func=_get)
    standard = match_by_pattern(json_data, r".*/Storage/[^/#]+/Controllers/[^/#]+$", func=_get)

    def serial(item):
        value = str(item.get("SerialNumber") or "").strip().upper()
        return "" if value in {"UNKNOWN", "N/A", "NONE", "NULL"} else value

    def controller_slot(item):
        location = item.get("Location")
        if isinstance(location, dict):
            location = (location.get("PartLocation") or {}).get("ServiceLabel")
        match = re.fullmatch(r"Slot[ =]+(\d+)", str(location), re.IGNORECASE)
        return match.group(1) if match else None

    for controller in standard:
        # NS204i exposes different serials in the HPE and standard views.
        existing = next((item for item in controllers if
                         (serial(controller) and serial(item) == serial(controller)) or
                         (controller_slot(controller) is not None and
                          controller_slot(item) == controller_slot(controller) and
                          item.get("Model") == controller.get("Model"))), None)
        if existing is None:
            controllers.append(controller)
        else:
            for field, value in controller.items():
                if existing.get(field) in (None, "") and value is not None:
                    existing[field] = value

    # The device inventory often carries the service P/N omitted by SmartStorage.
    for controller in controllers:
        if not controller.get("PartNumber") and serial(controller):
            for path, device in json_data.items():
                if (re.fullmatch(r".*/Devices/[^/#]+", path) and isinstance(device, dict)
                        and not is_absent(device) and serial(device) == serial(controller)):
                    controller["PartNumber"] = device.get("PartNumber")

    standard_disks = match_by_pattern(json_data, r".*/Storage/[^/#]+/Drives/[^/#]+$", func=sub_DiskDrives)
    unique_disks = []
    seen_disks = {}
    for disk in Disks + standard_disks:
        key = serial(disk)
        if key and key in seen_disks:
            for field, value in disk.items():
                if seen_disks[key].get(field) in (None, "") and value is not None:
                    seen_disks[key][field] = value
        else:
            unique_disks.append(disk)
            if key:
                seen_disks[key] = disk
    return stripJSON(controllers), stripJSON(unique_disks)


def get_storage_enclosures(json_data):
    result = []
    for path, data in json_data.items():
        if (re.fullmatch(r".*/StorageEnclosures/[^/#]+", path)
                and isinstance(data, dict) and not is_absent(data)
                and (data.get("Model") or data.get("SerialNumber"))):
            result.append(dict(data, **component_fields(data)))
    return stripJSON(result)

