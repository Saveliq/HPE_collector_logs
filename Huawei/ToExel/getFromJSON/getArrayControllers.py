from search import Resources, as_dict, as_list, huawei, identifier, first_value, scaled, unique_components


def _storage(resources):
    return resources.children(resources.system_path, "Storages") + resources.children(resources.system_path, "Storage")


def get_array_controllers(json_data):
    resources = Resources(json_data)
    controllers, drives, used_boards = [], resources.children(resources.chassis_path, "Drives"), set()
    for storage in _storage(resources):
        path = storage.get("@odata.id", "")
        nodes = resources.children(path, "Controllers") or as_list(storage.get("StorageControllers"))
        drives += as_list(storage.get("Drives")) + resources.children(path, "Drives")
        for controller in resources.installed(nodes):
            oem = huawei(controller)
            # AssociatedCard is the controller FRU; Links.Chassis is not.
            board = resources.resolve(oem.get("AssociatedCard"))
            if board.get("DeviceType") == "RAIDCard":
                used_boards.add(board.get("@odata.id"))
                controller["PhysicalKey"] = board.get("@odata.id")
                for field in ("SerialNumber", "PartNumber"):
                    controller[field] = identifier(controller.get(field), board.get(field))
                controller["Model"] = first_value(board.get("ProductName"), controller.get("Model"))
            controller["CurrentOperatingMode"] = oem.get("Mode")
            controller["CacheMemorySizeMiB"] = first_value(
                as_dict(controller.get("CacheSummary")).get("TotalCacheSizeMiB"), oem.get("MemorySizeMiB"))
            controllers.append(controller)
    # A board-only dump still identifies installed RAID cards.
    for board in resources.boards():
        if board.get("DeviceType") == "RAIDCard" and board.get("SourcePath") not in used_boards:
            board["Model"] = first_value(board.get("ProductName"), board.get("Description"))
            controllers.append(board)
    disks = resources.installed(drives)
    for disk in disks:
        disk.update(PartNumber=identifier(disk.get("PartNumber"), huawei(disk).get("OriginalPartNumber"), disk.get("Model")),
                    CapacityGB=scaled(disk.get("CapacityBytes"), 1 / 1e9),
                    InterfaceType=disk.get("Protocol"), InterfaceSpeedMbps=scaled(disk.get("NegotiatedSpeedGbs"), 1000),
                    FirmwareVersion=first_value(disk.get("FirmwareVersion"), disk.get("Revision")))
    return unique_components(controllers), disks


def get_storage_enclosures(json_data):
    resources = Resources(json_data)
    result = []
    for board in resources.boards():
        if board.get("DeviceType") != "DiskBackplane":
            continue
        board.update(ComponentName="Дисковая корзина (backplane)",
                     Model=first_value(board.get("BoardName"), board.get("Description")),
                     Comment=board.get("Description"),
                     FirmwareVersion=("CPLD: " + str(board["CPLDVersion"])) if board.get("CPLDVersion") else None)
        result.append(board)
    return unique_components(result)
