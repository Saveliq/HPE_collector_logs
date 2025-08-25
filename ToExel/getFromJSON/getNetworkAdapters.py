import re

from search import search_one, stripJSON


def get_network_adapters(json_data):
    def _get(data):
        node_result = {}
        node_result["Name"] = search_one(data, r"Name")
        node_result["PartNumber"] = search_one(data, r"PartNumber")
        node_result["SerialNumber"] = search_one(data, r"SerialNumber")
        return node_result
    result = []
    pattern = re.compile(r".*/NetworkAdapters/[0-9]{1,2}.*")
    nodes = {
        key: val for key, val in json_data.items() if pattern.match(key)
    }
    ind = 0
    for key, data in nodes.items():
        result.append(_get(data))
        ind += 1

    return stripJSON(result)

