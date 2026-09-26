import re

from search import search_one, stripJSON


def get_PCI_slots(json_data):
    def _get(data):
        node_result = {}
        node_result["Name"] = search_one(data, r"Name")
        node_result["Status"] = search_one(data, r"Status", path_pattern=r"OperationalStatus", value_type=str)
        return node_result
    result = {}
    pattern = re.compile(r".*/PCISlots/\d+(-\d+)?$")
    nodes = {
        key: val for key, val in json_data.items() if pattern.match(key)
    }

    for key, data in nodes.items():
        result["NetworkAdapter_" + key[-1]]= _get(data)

    return stripJSON(result)

