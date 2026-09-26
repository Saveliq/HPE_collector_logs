from search import Resources, first_value, unique_components
from getFromJSON.getNetworkAdapters import network_inventory


def get_PCI_slots(json_data):
    resources = Resources(json_data)
    _, used_pcie, used_boards, integrated = network_inventory(resources)
    boards = []
    for board in resources.boards():
        kind = board.get("DeviceType")
        if kind in {"RAIDCard", "DiskBackplane"} or board["SourcePath"] in used_boards:
            continue
        board["ComponentName"] = {"MainBoard": "Системная плата", "PCIeRiserCard": "PCIe райзер"}.get(kind, "Плата")
        board["Model"] = first_value(board.get("BoardName"), board.get("ProductName"), board.get("Description"))
        board["Comment"] = "; ".join(str(v) for v in (board.get("Description"), integrated.get(board["SourcePath"])) if v)
        if board.get("CPLDVersion"):
            board["FirmwareVersion"] = "CPLD: " + str(board["CPLDVersion"])
        boards.append(board)
    for device in resources.installed(resources.children(resources.chassis_path, "PCIeDevices")):
        if device["SourcePath"] not in used_pcie:
            device["ComponentName"] = "PCIe устройство"
            device["Model"] = first_value(device.get("Model"), device.get("Description"))
            boards.append(device)
    return {"Boards": unique_components(boards)}
