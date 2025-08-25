from search import search_one, stripJSON


def get_chassis(json_data):
    result = {}
    data = json_data['/redfish/v1/Chassis/1']
    result["ChassisType"] = search_one(data, r"ChassisType", consonants_only=True)
    result["BayNumber"] = search_one(data, r"BayNumber", consonants_only=True)
    result["Model"] = search_one(data, r"Model", consonants_only=True, value_pattern="ProLiant")
    result["SKU"] = search_one(data, r"SKU")
    result["SerialNumber"] = search_one(data, r"SerialNumber", value_pattern=r"^\s*.{1,12}\s*$", value_type=str,)
    result["ServerHealth"] = search_one(data, r"Health")
    result["ServerState"] = search_one(data, r"State")
    result["StorageBattery"] = search_one(data, r"PartNumber", path_pattern=r"SmartStorageBattery")
    return stripJSON(result)

