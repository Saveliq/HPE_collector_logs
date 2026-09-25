from search import search_one, stripJSON


def get_system(json_data):
    result = {}
    data = json_data.get('/redfish/v1/Systems/1', {})
    status = data.get("Status") or {}
    oem = data.get("Oem") or {}
    hpe = oem.get("Hpe") or oem.get("Hp") or {}
    result["ServerHealth"] = status.get("Health")
    result["ServerState"] = status.get("State")
    result["ServerHealthRollup"] = status.get("HealthRollup")
    result["PowerState"] = data.get("PowerState")
    result["PowerRegulatorMode"] = hpe.get("PowerRegulatorMode")
    result["PowerAutoOn"] = hpe.get("PowerAutoOn")
    result["BiosVersion"] = search_one(data, r"BiosVersion")
    result["MemorySummary"] = search_one(data, r"HealthRollup", path_pattern="MemorySummary")
    result["TotalSystemMemoryGiB"] = search_one(data, r"TotalSystemMemoryGiB", path_pattern="MemorySummary")
    result["TrustedModules"] = search_one(data, r"Statu", path_pattern="TrustedModules", consonants_only=True, value_type=str)
    result["ProcessorModel"] = search_one(data, r"Model", path_pattern=r"ProcessorSummary", consonants_only=True)
    result["ProcessorCount"] = search_one(data, r"Count", path_pattern=r"ProcessorSummary", consonants_only=True)
    return stripJSON(result)

