from search import CHASSIS, Resources, _dict, stripJSON
from getFromJSON.getChassis import _chassis_components


def get_power(json_data):
    return stripJSON(_chassis_components(
        Resources(json_data), "/Power", "PowerSupplies", "/PowerSubsystem/PowerSupplies"))


def _number(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def get_power_consumption(json_data):
    """Return current chassis power consumption in watts.

    Prefer the modern EnvironmentMetrics.PowerWatts.Reading resource.  Older
    iDRAC generations in the same fleet may not expose PowerWatts there, so
    keep the legacy Chassis/Power.PowerControl fallback.
    """
    environment = json_data.get(CHASSIS + "/EnvironmentMetrics")
    if isinstance(environment, dict):
        reading = _number(_dict(environment.get("PowerWatts")).get("Reading"))
        if reading is not None:
            return reading

    path = CHASSIS + "/Power"
    sources = [path] + sorted(key for key in json_data if key.startswith(path + "#PowerControl"))
    for source in sources:
        body = json_data.get(source)
        controls = body.get("PowerControl", body) if isinstance(body, dict) else body
        if isinstance(controls, dict):
            controls = [controls]
        if not isinstance(controls, list):
            continue
        controls = [item for item in controls if isinstance(item, dict) and "PowerConsumedWatts" in item]
        if len(controls) > 1:
            controls = [item for item in controls if str(item.get("MemberId")) == "0"
                        or item.get("PhysicalContext") == "Chassis"]
        if len(controls) == 1:
            value = _number(controls[0].get("PowerConsumedWatts"))
            if value is not None:
                return value
    return None
