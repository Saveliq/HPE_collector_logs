"""Fleet aggregation without counting Redfish aliases as extra hardware."""
from collections import defaultdict
import re

from diagnostic_sheets import display_value
from search import is_absent


COMPONENT_LISTS = {
    "Processors": "Процессор", "Memory": "Память", "NetworkAdapters": "Сетевой адаптер",
    "SmartStorage": "Контроллер хранения", "PhysicalDisks": "Диск", "PowerSupplies": "Блок питания",
    "StorageBatteries": "RAID батарея", "StorageEnclosures": "Дисковая полка",
    "Fans": "Вентилятор", "USBDevices": "USB устройство", "TrustedModules": "TrustedModule",
}


def text(value):
    value = display_value(value)
    return "" if value is None else str(value)


def unhealthy(value):
    return value is not None and str(value).strip().lower() not in {"", "ok", "none", "null", "n/a"}


def component_type(item, default="Компонент"):
    path = text(item.get("ComponentPath") or item.get("SourcePath"))
    name = " ".join(text(item.get(field)) for field in ("Name", "Model", "DeviceType", "AdapterType")).lower()
    if default == "Диск" or re.search(r"/(?:Drives|DiskDrives|UnconfiguredDrives)/", path):
        media = text(item.get("MediaType")).upper()
        return media if media in {"SSD", "HDD"} else "Диск"
    if "/FC." in path or any(word in name for word in ("fibre channel", "fiber channel", " fc ", "fc32", "fchba")):
        return "FC HBA"
    if "boss" in name or "boot controller" in name:
        return "Загрузочный контроллер"
    if default != "Компонент":
        return default
    if path in {"/redfish/v1/Chassis/System.Embedded.1", "/redfish/v1/Systems/System.Embedded.1"}:
        return "Системный микрокод"
    for fragment, kind in (("/Processors/", "Процессор"), ("/Memory/", "Память"),
                           ("PowerSupplies/", "Блок питания"), ("SmartStorageBattery/", "RAID батарея"),
                           ("/StorageEnclosures/", "Дисковая полка"), ("/Fans/", "Вентилятор"),
                           ("/Temperatures/", "Датчик температуры"), ("/ArrayControllers/", "Контроллер хранения"),
                           ("/NetworkAdapters/", "Сетевой адаптер"), ("/BaseNetworkAdapters/", "Сетевой адаптер")):
        if fragment in path:
            return kind
    if "boss" in name or "boot controller" in name:
        return "Загрузочный контроллер"
    if "perc" in name or "smart array" in name or "raid" in name:
        return "RAID контроллер"
    if "hba" in name or "nonraid" in name or "non-raid" in name:
        return "HBA контроллер"
    if "ahci" in name or "sata controller" in name or "ssata controller" in name:
        return "SATA/AHCI контроллер"
    if "ethernet" in name or "network" in name:
        return "Сетевой адаптер"
    return text(item.get("DeviceType")) or default


def inventory_components(server):
    components = []
    for field, kind in COMPONENT_LISTS.items():
        seen = set()
        for index, item in enumerate(server.get(field) or []):
            if not isinstance(item, dict) or is_absent(item):
                continue
            serial = text(item.get("SerialNumber")).upper()
            key = (field, serial or text(item.get("SourcePath")) or index)
            if key in seen:
                continue
            seen.add(key)
            components.append(dict(item, ComponentType=component_type(item, item.get("ComponentName") or kind), InstanceKey=key))
    return components


def _slot(item):
    location = item.get("Location")
    if isinstance(location, dict):
        location = (location.get("PartLocation") or {}).get("ServiceLabel")
    match = re.fullmatch(r"Slot[ =]+(\d+)", str(location), re.IGNORECASE)
    return match.group(1) if match else None


def _resolve(item, components):
    path = text(item.get("ComponentPath") or item.get("SourcePath"))
    serial = text(item.get("SerialNumber")).upper()
    fqdd = text(item.get("FQDD"))
    pcie = re.search(r"/PCIeDevices/([^/#]+)", path)
    for component in components:
        addresses = [text(component.get("SourcePath"))] + (component.get("SourceAliases") or [])
        identifiers = [text(component.get("Id"))] + [address.rsplit("/", 1)[-1] for address in addresses]
        if ((path and any(address and (path == address or path.startswith(address + "#")
                                      or path.startswith(address + "/Oem/")) for address in addresses))
                or (pcie and any(re.search(r"/PCIeDevices/" + re.escape(pcie.group(1)) + r"(?:/|$)", address)
                                 for address in addresses))
                or (fqdd and any(identifier and (fqdd == identifier or fqdd.startswith(identifier + "-"))
                                 for identifier in identifiers))
                or (serial not in {"", "0", "UNKNOWN", "N/A"} and serial == text(component.get("SerialNumber")).upper())
                or (_slot(item) is not None and _slot(item) == _slot(component)
                    and text(item.get("Model")) and text(item.get("Model")) == text(component.get("Model")))):
            resolved = dict(item)
            resolved.update({key: value for key, value in component.items() if value not in (None, "")})
            return resolved
    if fqdd:
        # Current/Installed/Previous are snapshots of the same software element.
        return dict(item, ComponentType="Системный микрокод", InstanceKey=("Software", fqdd))
    kind = component_type(item)
    return dict(item, ComponentType=kind, InstanceKey=(kind, serial or path))


def _identity_label(component):
    if component.get("InstanceKey", (None,))[0] == "Software":
        # Package display names may include their version; group by the package.
        family = text(component.get("FQDD")).split(".", 1)[0]
        package_names = {"ServiceModule": "Dell iDRAC Service Module", "DriverPack": "Dell OS Driver Pack",
                         "Diagnostics": "Dell uEFI Diagnostics", "iDRAC": "iDRAC",
                         "USC": "Lifecycle Controller"}
        if family in package_names:
            return package_names[family]

    def product_name(value):
        # Dell embeds a port MAC in some product names (and P/N fallbacks).
        # It identifies an instance, not a component model for fleet grouping.
        return re.sub(r"\s+-\s+(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$", "", text(value))

    model = product_name(component.get("Model") or component.get("ProductName"))
    part = product_name(component.get("PartNumber") or component.get("SparePartNumber"))
    return " / ".join(dict.fromkeys(value for value in (model, part) if value)) or product_name(component.get("Name"))


def _firmware_role(field):
    if field.startswith("MicrocodePatches/"):
        return "Доступный патч CPU, CpuId=" + field.split("/", 1)[1]
    if field.startswith("Microcode"):
        return field
    suffix = field.split("/")[1:]
    if not suffix or suffix == ["Current"]:
        return "Текущая"
    return "/".join(suffix)


def firmware_records(server):
    components = inventory_components(server)
    records = {}

    def add(component, version, role):
        # A physical device can expose the same version through several APIs.
        key = (component["InstanceKey"], text(version), role)
        records.setdefault(key, dict(component, Version=text(version), FirmwareRole=role))

    for component in components:
        if text(component.get("FirmwareVersion")):
            add(component, component["FirmwareVersion"], "Текущая")
    current_instances = {record["InstanceKey"] for record in records.values()}
    for item in server.get("FirmwareInventory", []):
        field = item.get("Field", "")
        path = text(item.get("ComponentPath") or item.get("SourcePath"))
        if (field in {"BiosVersion", "ManagerFirmwareVersion"}
                or path == "/redfish/v1/Managers/iDRAC.Embedded.1" or item.get("Absent") or not text(item.get("Version"))):
            continue
        component = _resolve(item, components)
        role = item.get("FirmwareRole") or _firmware_role(field)
        # Prefer the parsed inventory's current version and identity; OEM backups
        # and CPU patches remain separate rows, never additional physical devices.
        if role == "Текущая" and component["InstanceKey"] in current_instances:
            continue
        add(component, item.get("Version"), role)
    represented = {record["InstanceKey"] for record in records.values()}
    for component in components:
        if component["InstanceKey"] not in represented:
            add(component, None, "Текущая")
    return list(records.values())


def firmware_groups(servers):
    groups = defaultdict(lambda: {"servers": set(), "components": set()})
    for server_index, server in enumerate(servers):
        for item in firmware_records(server):
            key = (item["ComponentType"], _identity_label(item), item["Version"], item["FirmwareRole"])
            groups[key]["servers"].add(server_index)
            groups[key]["components"].add((server_index, item["InstanceKey"]))
    return groups


def health_issues(server):
    components = inventory_components(server)
    issues = {}

    def add(item, component, field="Status"):
        if not any(unhealthy(item.get(key)) for key in ("Health", "HealthRollup")):
            return
        key = (component["InstanceKey"], field, item.get("Health"), item.get("HealthRollup"))
        issue = dict(component)
        issue.update({key: item.get(key) for key in ("State", "Health", "HealthRollup")})
        issue["SourcePath"] = item.get("SourcePath") or component.get("SourcePath")
        issues.setdefault(key, issue)

    server_component = {"ComponentType": "Сервер", "Name": "Сервер", "Model": server.get("Model"),
                        "SerialNumber": server.get("SerialNumber"), "ServiceTag": server.get("ServiceTag"),
                        "PartNumber": server.get("PartNumber") or server.get("SKU"),
                        "FirmwareVersion": "; ".join(f"{label}: {text(server.get(field))}" for label, field in
                            (("BIOS", "BiosVersion"), ("iDRAC", "iDRACVersion")) if text(server.get(field))),
                        "InstanceKey": ("Server", "/redfish/v1/Systems/System.Embedded.1"), "SourcePath": "/redfish/v1/Systems/System.Embedded.1"}
    add({"Health": server.get("ServerHealth"), "HealthRollup": server.get("ServerHealthRollup"),
         "State": server.get("ServerState")}, server_component)
    for item in components:
        add(item, item)
    for item in server.get("ComponentStatus", []):
        path = item.get("SourcePath")
        # License health is not hardware health. These records have no hardware
        # P/N or S/N and must not flag an otherwise healthy server as faulty.
        if any(part.lower() in {"licenseservice", "licenses", "delllicenses", "delllicense"}
               for part in text(path).split("/")):
            continue
        if path == "/redfish/v1/Systems/System.Embedded.1":
            component = server_component
        elif path == "/redfish/v1/Chassis/System.Embedded.1":
            component = dict(server_component, ComponentType="Сервер (шасси)", InstanceKey=("Server", path))
        else:
            component = _resolve(item, components)
        add(item, component, item.get("Field", "Status"))
    return list(issues.values())
