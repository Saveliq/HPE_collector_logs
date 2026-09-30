import re

from search import search_one, stripJSON
from getFromJSON.getDiagnostics import component_fields


def get_power_consumption(json_data):
    """Read chassis consumption, never PSU capacity or a sum of overlapping domains.

    Collectors can save either the Power response or a resolved #PowerControl
    fragment. Prefer the base response when both snapshots are present.
    """
    path = "/redfish/v1/Chassis/1/Power"
    sources = [path] + sorted(key for key in json_data if key.startswith(path + "#PowerControl"))
    for source in sources:
        body = json_data.get(source)
        controls = body.get("PowerControl", body) if isinstance(body, dict) else body
        if isinstance(controls, dict):
            controls = [controls]
        if not isinstance(controls, list):
            continue
        controls = [item for item in controls if isinstance(item, dict) and "PowerConsumedWatts" in item]
        if len(controls) > 1:
            controls = [item for item in controls if str(item.get("MemberId")) == "0"
                        or item.get("PhysicalContext") == "Chassis"]
        if len(controls) == 1:
            value = controls[0].get("PowerConsumedWatts")
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return value
    return None


def get_power(json_data):
    def _parse_power_supply(data):
        node_result = {}
        node_result["Name"] = search_one(data, r"Name")
        node_result["Model"] = search_one(data, r"Model")
        node_result["PartNumber"] = search_one(data, r"PartNumber")
        node_result["SparePartNumber"] = search_one(data, r"SparePartNumber")
        node_result["SerialNumber"] = search_one(data, r"SerialNumber")
        node_result["PowerCapacityWatts"] = search_one(data, r"PowerCapacityWatts")
        node_result["State"] = search_one(data, r"State", path_pattern="Status")
        node_result["Health"] = search_one(data, r"Health", path_pattern="Status")
        node_result.update(component_fields(data))
        return node_result

    result = []
    power_pattern = re.compile(r".*/Power(/\d+(-\d+)?)?$")
    power_nodes = {
        key: val for key, val in json_data.items() if power_pattern.match(key)
    }

    for path, data in power_nodes.items():
        if isinstance(data, dict) and isinstance(data.get("PowerSupplies"), list):
            for index, power_supply in enumerate(data["PowerSupplies"]):
                result.append(dict(_parse_power_supply(power_supply), SourcePath=f"{path}#/PowerSupplies/{index}"))
        elif isinstance(data, dict) and ("PowerSupplyType" in data or "SerialNumber" in data):
            result.append(dict(_parse_power_supply(data), SourcePath=path))

    return stripJSON(result)

