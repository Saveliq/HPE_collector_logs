from search import search_one, stripJSON


def get_system(json_data):
    result = {}
    data = json_data['/redfish/v1/Systems/1']
    result["BiosVersion"] = search_one(data, r"BiosVersion")
    result["MemorySummary"] = search_one(data, r"HealthRollup", path_pattern="MemorySummary")
    result["TotalSystemMemoryGiB"] = search_one(data, r"TotalSystemMemoryGiB", path_pattern="MemorySummary")
    result["TrustedModules"] = search_one(data, r"Statu", path_pattern="TrustedModules", consonants_only=True, value_type=str)
    result["ProcessorModel"] = search_one(data, r"Model", path_pattern=r"ProcessorSummary", consonants_only=True)
    result["ProcessorCount"] = search_one(data, r"Count", path_pattern=r"ProcessorSummary", consonants_only=True)
    return stripJSON(result)

