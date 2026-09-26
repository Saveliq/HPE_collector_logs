from search import search_one, stripJSON


def get_manager(json_data):
    result = {}
    data = json_data.get('/redfish/v1/Managers/1', {})
    result["iLOVersion"] = data.get("FirmwareVersion")
    result["iLOSelfTestResults"] = search_one(data, r"iLOSelfTestResults", consonants_only=True)
    return stripJSON(result)

