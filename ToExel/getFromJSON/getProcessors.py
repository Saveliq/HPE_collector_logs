import re

from search import search_one, stripJSON


def get_processors(json_data):
    def _get(data):
        node_result = {}
        node_result["Name"] = search_one(data, r"Name")
        node_result["Model"] = search_one(data, r"Model")
        node_result["PartNumber"] = search_one(data, r"PartNumber")
        node_result["SerialNumber"] = search_one(data, r"SerialNumber")
        node_result["Manufacturer"] = search_one(data, r"Manufacturer")
        node_result["State"] = search_one(data, r"State", path_pattern=r"Status")
        node_result["Health"] = search_one(data, r"Health", path_pattern=r"Status")
        return node_result

    result = []
    pattern = re.compile(r".*/Processors/\d+(-\d+)?$")
    nodes = {
        key: val for key, val in json_data.items() if pattern.match(key)
    }

    for _, data in nodes.items():
        result.append(_get(data))

    return stripJSON(result)
