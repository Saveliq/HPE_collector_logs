import re

from search import search_one, stripJSON


INVALID_VALUES = {"", "n/a", "na", "none", "null", "unknown"}


def _normalize_value(value):
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() in INVALID_VALUES:
        return ""
    return text

def _is_nic_device(data):
    device_type = _normalize_value(search_one(data, r"DeviceType"))
    name = _normalize_value(search_one(data, r"Name"))
    return (
        "NIC" in device_type.upper()
        or "LOM" in device_type.upper()
        or "ETHERNET" in name.upper()
        or "NETWORK" in name.upper()
    )

def _parse_adapter(data, source_path):
    part_number = _normalize_value(search_one(data, r"PartNumber"))
    if not part_number:
        part_number = _normalize_value(search_one(data, r"ProductPartNumber"))
    if not part_number:
        part_number = _normalize_value(search_one(data, r"SKU"))

    serial_number = _normalize_value(search_one(data, r"SerialNumber"))
    if not serial_number:
        serial_number = _normalize_value(search_one(data, r"PCASerialNumber"))

    firmware_version = search_one(data, r"VersionString", path_pattern=r"FirmwareVersion")
    if firmware_version is None:
        firmware_version = _normalize_value(search_one(data, r"FirmwareVersion"))

    return {
        "Name": _normalize_value(search_one(data, r"Name")),
        "PartNumber": part_number,
        "SerialNumber": serial_number,
        "Model": _normalize_value(search_one(data, r"Model")),
        "FirmwareVersion": _normalize_value(firmware_version),
        "Location": _normalize_value(search_one(data, r"Location")),
        "SourcePath": source_path,
    }


def get_network_adapters(json_data):
    result = []
    seen = set()

    direct_adapter_pattern = re.compile(r".*/(NetworkAdapters|BaseNetworkAdapters)/\d+(-\d+)?$")
    device_pattern = re.compile(r".*/Devices/\d+(-\d+)?$")
    pcie_pattern = re.compile(r".*/PCIeDevices/\d+(-\d+)?$")

    for key, data in json_data.items():
        if not isinstance(data, dict):
            continue

        include = False
        if direct_adapter_pattern.match(key):
            include = True
        elif device_pattern.match(key) and _is_nic_device(data):
            include = True
        elif pcie_pattern.match(key) and _is_nic_device(data):
            include = True

        if not include:
            continue

        adapter = _parse_adapter(data, key)
        if not adapter.get("Name") and not adapter.get("PartNumber") and not adapter.get("SerialNumber"):
            continue

        serial_key = adapter.get("SerialNumber", "").upper()
        if serial_key:
            dedupe_key = ("SN", serial_key)
        else:
            dedupe_key = (
                "FALLBACK",
                adapter.get("PartNumber", "").upper(),
                adapter.get("Name", "").upper(),
                adapter.get("Model", "").upper(),
            )

        if dedupe_key in seen:
            continue

        seen.add(dedupe_key)
        result.append(adapter)

    return stripJSON(result)

