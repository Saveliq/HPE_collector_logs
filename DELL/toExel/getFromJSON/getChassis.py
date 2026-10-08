import re

from search import SYSTEM, CHASSIS, Resources, _dict, _list, _first, _installed, stripJSON


ROOT = "/redfish/v1"


def _chassis_components(resources, parent, field, modern_path):
    # Prefer modern resources, so the legacy array does not double-count them.
    nodes = resources.matching(re.escape(CHASSIS + modern_path) + r"/[^/]+")
    if not nodes:
        nodes = [dict(node, SourcePath=node.get("@odata.id") or f"{CHASSIS}{parent}#/{field}/{index}")
                 for index, node in enumerate(_list(resources.data.get(CHASSIS + parent, {}).get(field)))
                 if isinstance(node, dict)]
    return _installed(resources, nodes)


def _service_tag(resources, system):
    """Return Dell Service Tag without overloading standard SerialNumber.

    Dell exposes the Service Tag at the Redfish service root as
    Oem.Dell.ServiceTag.  System.SKU is kept only as a compatibility fallback
    for older iDRAC generations that do not expose the OEM root field.
    """
    root = _dict(resources.data.get(ROOT, {}))
    dell = _dict(_dict(root.get("Oem")).get("Dell"))
    return _first(dell.get("ServiceTag"), system.get("SKU"))


def get_chassis(json_data):
    resources = Resources(json_data)
    system = resources.data.get(SYSTEM, {})
    chassis = resources.data.get(CHASSIS, {})
    batteries = resources.matching(re.escape(SYSTEM) + r"/Storage/[^/]+/Oem/Dell/DellControllerBattery/[^/]+")
    batteries += resources.matching(re.escape(CHASSIS) + r"/PowerSubsystem/Batteries/[^/]+")
    batteries = _installed(resources, batteries)
    for battery in batteries:
        battery["Health"] = _first(battery.get("Health"), battery.get("PrimaryStatus"))

    part_number = _first(system.get("PartNumber"), chassis.get("PartNumber"))
    return stripJSON({
        "Model": _first(system.get("Model"), chassis.get("Model")),
        # Keep standards-based chassis/system serial separate from Dell Service Tag.
        "SerialNumber": _first(system.get("SerialNumber"), chassis.get("SerialNumber")),
        "ServiceTag": _service_tag(resources, system),
        # Historical key kept for compatibility with the existing Excel writer.
        # It represents the server P/N, not the Redfish SKU/Service Tag.
        "PartNumber": part_number,
        "SKU": _first(part_number, system.get("SKU")),
        "Fans": _chassis_components(resources, "/Thermal", "Fans", "/ThermalSubsystem/Fans"),
        "StorageBatteries": batteries,
    })
