import re

from search import Resources, as_list, first_value, identifier, is_absent, scaled, unique_components


def _fans(resources):
    nodes = resources.children(resources.chassis_path, "ThermalSubsystem/Fans")
    if not nodes:
        nodes = as_list(resources.resolve(resources.chassis_path + "/Thermal").get("Fans"))
    if nodes:
        return resources.installed(nodes)
    # Some iBMC dumps omit Thermal. Named RPM sensors establish fan records;
    # maximum slot counts and undecoded hex presence masks do not.
    fans = []
    source = resources.chassis_path + "/ThresholdSensors"
    for sensor in as_list(resources.resolve(source).get("Sensors")):
        if not isinstance(sensor, dict):
            continue
        match = re.fullmatch(r"FAN\s*(\d+) Speed", str(sensor.get("Name", "")), re.IGNORECASE)
        reading = scaled(sensor.get("ReadingValue"), 1)
        if not match or sensor.get("Unit") != "RPM" or reading is None or is_absent(sensor.get("Status")):
            continue
        fans.append({"Name": "FAN" + match.group(1), "Reading": reading,
                     "SourcePath": source + "#FAN" + match.group(1), "Health": sensor.get("Status"),
                     "Comment": f"Датчик {sensor['Name']}: {reading:g} RPM; P/N и S/N не указаны"})
    return unique_components(fans)


def get_chassis(json_data):
    resources = Resources(json_data)
    system = resources.resolve(resources.system_path)
    chassis = resources.resolve(resources.chassis_path)
    return {
        "Model": first_value(system.get("Model"), chassis.get("Model")),
        "SerialNumber": identifier(system.get("SerialNumber"), chassis.get("SerialNumber")),
        "SKU": identifier(system.get("PartNumber"), chassis.get("PartNumber"), system.get("SKU")),
        "Fans": _fans(resources),
        "StorageBatteries": resources.installed(resources.children(resources.chassis_path, "BackupBatteryUnits")),
    }
