import re

from search import SYSTEM, MANAGER, Resources, _installed, stripJSON


def get_embedded_media(json_data):
    resources = Resources(json_data)
    nodes = resources.matching(re.escape(SYSTEM) + r"/USBDevices/[^/]+")
    nodes += resources.matching(re.escape(MANAGER) + r"/USBDevices/[^/]+")
    return stripJSON({"USBDevices": _installed(resources, nodes)})
