import re

from search import search_one, stripJSON


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
        return node_result

    result = []
    power_pattern = re.compile(r".*/Power(/\d+(-\d+)?)?$")
    power_nodes = {
        key: val for key, val in json_data.items() if power_pattern.match(key)
    }

    for _, data in power_nodes.items():
        if isinstance(data, dict) and isinstance(data.get("PowerSupplies"), list):
            for power_supply in data["PowerSupplies"]:
                result.append(_parse_power_supply(power_supply))
        elif isinstance(data, dict):
            result.append(_parse_power_supply(data))

    return stripJSON(result)

