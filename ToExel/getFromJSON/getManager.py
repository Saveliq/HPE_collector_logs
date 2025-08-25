from search import search_one, stripJSON


def get_manager(json_data):
    result = {}
    data = json_data['/redfish/v1/Managers/1']
    result["iLOVersion"] = search_one(data, r"FirmwareVersion", consonants_only=True, value_pattern=r"iLO")
    result["iLOSelfTestResults"] = search_one(data, r"iLOSelfTestResults", consonants_only=True)
    return stripJSON(result)

