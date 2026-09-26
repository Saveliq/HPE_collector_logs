from search import search_one, stripJSON, is_absent
from getFromJSON.getDiagnostics import component_fields


def get_chassis(json_data):
    result = {}
    data = json_data['/redfish/v1/Chassis/1']
    result["ChassisType"] = search_one(data, r"ChassisType", consonants_only=True)
    result["BayNumber"] = search_one(data, r"BayNumber", consonants_only=True)
    result["Model"] = data.get("Model")
    result["SKU"] = search_one(data, r"SKU")
    result["SerialNumber"] = search_one(data, r"SerialNumber", value_pattern=r"^\s*.{1,12}\s*$", value_type=str,)
    result["ServerHealth"] = search_one(data, r"Health")
    result["ServerState"] = search_one(data, r"State")
    result["StorageBattery"] = search_one(data, r"PartNumber", path_pattern=r"SmartStorageBattery")
    oem = data.get("Oem") or {}
    hpe = oem.get("Hpe") or oem.get("Hp") or {}
    result["StorageBatteries"] = [dict(battery, **component_fields(battery))
                                for battery in (hpe.get("SmartStorageBattery") or [])
                                if isinstance(battery, dict) and not is_absent(battery)]
    thermal = json_data.get('/redfish/v1/Chassis/1/Thermal') or {}
    result["Fans"] = []
    for fan in thermal.get("Fans") or []:
        if not isinstance(fan, dict) or is_absent(fan):
            continue
        fan_oem = fan.get("Oem") or {}
        fan_hpe = fan_oem.get("Hpe") or fan_oem.get("Hp") or {}
        if str(fan_hpe.get("Location", "")).strip().lower() != "virtual":
            result["Fans"].append(dict(fan, **component_fields(fan)))
    return stripJSON(result)

