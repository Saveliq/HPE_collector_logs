import re

from search import search_one, stripJSON

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
        node_result["DiskDriveStatusReasons"] = search_one(data, r"DiskDriveStatusReasons")
        node_result["InterfaceType"] = search_one(data, r"InterfaceType")
        node_result["FirmwareVersion"] = search_one(data, r"VersionString", path_pattern="FirmwareVersion")
        node_result["InterfaceSpeedMbps"] = search_one(data, r"InterfaceSpeedMbps")
        node_result["MediaType"] = search_one(data, r"MediaType")
        node_result["Model"] = search_one(data, r"Model")
        node_result["Health"] = search_one(data, r"Health", path_pattern="Status")
        node_result["State"] = search_one(data, r"State", path_pattern="Status")
        node_result["SerialNumber"] = search_one(data, r"SerialNumber")
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
        node_result["PartNumber"] = search_one(data, r"PartNumber")
        node_result["SerialNumber"] = search_one(data, r"SerialNumber")
        node_result["State"] = search_one(data, r"State", path_pattern=r"Status")
        node_result["Health"] = search_one(data, r"Health", path_pattern=r"Status")
        disk_drives = match_by_pattern(json_data, rf".*/ArrayControllers/{id_node}/DiskDrives/\d+(-\d+)?$", "Disk", func=sub_DiskDrives)
        node_result["DiskDrives"] = disk_drives
        Disks += disk_drives
        unconfigdisk_drives = match_by_pattern(json_data, rf".*/ArrayControllers/{id_node}/UnconfiguredDrives/\d+(-\d+)?$", "Disk",
                                       func=sub_DiskDrives)
        node_result["DiskDrives"] += unconfigdisk_drives
        Disks += unconfigdisk_drives
        print(Disks)
        disk_logical_drives = match_by_pattern(json_data, rf".*/ArrayControllers/{id_node}/LogicalDrives/\d+(-\d+)?$", "Logical_Disk",
                                       func=sub_LogicalDrives)
        node_result["LogicalDiskDrives"] = disk_logical_drives
        return node_result

    def match_by_pattern(data, pattern, descr="UNDEF", func=None):
        result = []
        pattern = re.compile(pattern)
        nodes = {
            key: val for key, val in data.items() if pattern.match(key)
        }
        ind = 0
        for key, _data in nodes.items():
            result.append(func(_data, int(key[-1])))
        return result


    return stripJSON(match_by_pattern(json_data, r".*/ArrayControllers/\d+(-\d+)?$", "ArrayController_", func=_get)), Disks

