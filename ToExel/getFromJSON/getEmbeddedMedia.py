from search import search_one, stripJSON


def get_embedded_media(json_data):
    result = {}
    data = json_data['/redfish/v1/Managers/1/EmbeddedMedia']
    result["SDCard"] = search_one(data, r"State", path_pattern="SDCard")
    return stripJSON(result)

