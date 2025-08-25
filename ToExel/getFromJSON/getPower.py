import re

from search import search_one, stripJSON


def get_power(json_data):
    def _get_power(data):
        pass
    result = []
    power_pattern = re.compile(r"/Power/\d+(-\d+)?$")
    power_nodes = {
        key: val for key, val in json_data.items() if power_pattern.match(key)
    }

    for key, data in power_nodes.items():

        result.append(_get_power(data))

    return stripJSON(result)

