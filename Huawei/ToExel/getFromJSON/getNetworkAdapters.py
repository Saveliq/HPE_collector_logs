import re

from search import Resources, as_dict, as_list, huawei, identifier, first_value, unique_components


def _product_name(value):
    value = identifier(value)
    return value if value and value.lower() not in {"pcie card", "lom", "network adapter"} else None


def _is_network_device(resources, device):
    oem = huawei(device)
    if oem.get("FunctionType") == "Net Card" or oem.get("PCIeCardType") in {"FC", "NIC"}:
        return True
    functions = resources.children(device.get("@odata.id", ""), "Functions")
    if any(fn.get("DeviceClass") == "NetworkController" for fn in functions):
        return True
    # Older firmware reports DeviceClass=Other for the Intel PRO/1000 card.
    return bool(re.search(r"Ethernet|Fibre Channel|Network Adapter|PRO/\d+", str(device.get("Description", "")), re.I))


def network_inventory(resources):
    adapters, used_pcie, used_boards, integrated = [], set(), set(), {}
    boards = resources.boards()
    nodes = resources.children(resources.chassis_path, "NetworkAdapters")
    # NetworkInterface is a view of NetworkAdapter, not another physical card.
    for interface in resources.children(resources.system_path, "NetworkInterfaces"):
        nodes.append(resources.resolve(as_dict(interface.get("Links")).get("NetworkAdapter")))
    for adapter in resources.installed(nodes):
        oem = huawei(adapter)
        board = next((b for b in boards if b.get("DeviceType") == "NICCard" and b.get("Id") == adapter.get("Id")), {})
        if board:
            used_boards.add(board["SourcePath"])
            mainboard = resources.integrated_mainboard(board)
            if mainboard:
                integrated[mainboard["@odata.id"]] = "; ".join(str(v) for v in
                    ("Встроенный LOM", adapter.get("Model"), oem.get("CardModel")) if v)
                continue
        devices, versions = [], []
        links = [as_dict(adapter.get("Links"))]
        for controller in as_list(adapter.get("Controllers")):
            version = identifier(as_dict(controller).get("FirmwarePackageVersion"))
            if version and version not in versions:
                versions.append(version)
            links.append(as_dict(as_dict(controller).get("Links")))
        for link in links:
            devices += resources.installed(as_list(link.get("PCIeDevices")))
        for device in devices:
            used_pcie.add(device["SourcePath"])
        # Only a single explicit PCIe association supplies card identity.
        unique_devices = unique_components(devices)
        device = unique_devices[0] if len(unique_devices) == 1 else {}
        adapter["PhysicalKey"] = first_value(device.get("SourcePath"), board.get("SourcePath"))
        model = first_value(_product_name(huawei(device).get("ProductName")),
                            _product_name(oem.get("Name")), adapter.get("Model"))
        adapter.update(Model=model, Name=first_value(model, device.get("Description"), adapter.get("Name")),
                       PartNumber=identifier(adapter.get("PartNumber"), board.get("PartNumber"),
                                             device.get("PartNumber"), _product_name(model)),
                       SerialNumber=identifier(adapter.get("SerialNumber"), board.get("SerialNumber"), device.get("SerialNumber")),
                       FirmwareVersion=first_value(adapter.get("FirmwareVersion"), "; ".join(versions), device.get("FirmwareVersion")))
        adapters.append(adapter)
    # Keep independently installed cards that iBMC omitted from NetworkAdapters.
    for device in resources.installed(resources.children(resources.chassis_path, "PCIeDevices")):
        if device["SourcePath"] in used_pcie or not _is_network_device(resources, device):
            continue
        used_pcie.add(device["SourcePath"])
        model = first_value(_product_name(huawei(device).get("ProductName")), device.get("Model"))
        device.update(Name=first_value(model, device.get("Description"), device.get("Name")), Model=model,
                      PartNumber=identifier(device.get("PartNumber"), _product_name(model)))
        adapters.append(device)
    # NIC boards that have no NetworkAdapter view still need one inventory row.
    for board in boards:
        if board.get("DeviceType") != "NICCard" or board["SourcePath"] in used_boards:
            continue
        used_boards.add(board["SourcePath"])
        mainboard = resources.integrated_mainboard(board)
        if mainboard:
            integrated[mainboard["@odata.id"]] = "Встроенный LOM: " + str(board.get("Description") or board.get("ProductName"))
        else:
            board["Name"] = first_value(board.get("ProductName"), board.get("Description"), board.get("Name"))
            adapters.append(board)
    return unique_components(adapters), used_pcie, used_boards, integrated


def get_network_adapters(json_data):
    return network_inventory(Resources(json_data))[0]
