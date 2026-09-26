from search import MANAGER, Resources, stripJSON


def get_manager(json_data):
    manager = Resources(json_data).data.get(MANAGER, {})
    return stripJSON({"iDRACVersion": manager.get("FirmwareVersion")})
