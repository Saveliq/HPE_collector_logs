import re

from search import SYSTEM, CHASSIS, Resources, _dict, _list, _first, _scaled, _installed, is_absent, stripJSON


def _chassis_components(resources, parent, field, modern_path):
    # Prefer modern resources, so the legacy array does not double-count them.
    nodes = resources.matching(re.escape(CHASSIS + modern_path) + r"/[^/]+")
    if not nodes:
        nodes = _list(resources.data.get(CHASSIS + parent, {}).get(field))
    return _installed(resources, nodes)


def get_chassis(json_data):
    resources = Resources(json_data)
    system = resources.data.get(SYSTEM, {})
    chassis = resources.data.get(CHASSIS, {})
    return stripJSON({
        "Model": _first(system.get("Model"), chassis.get("Model")),
        # Dell SKU is the service tag; the Excel P/N column needs PartNumber.
        "SKU": _first(system.get("PartNumber"), chassis.get("PartNumber"), system.get("SKU")),
        "SerialNumber": _first(system.get("SerialNumber"), chassis.get("SerialNumber"), system.get("SKU")),
        "Fans": _chassis_components(resources, "/Thermal", "Fans", "/ThermalSubsystem/Fans"),
        "StorageBatteries": [],
    })


