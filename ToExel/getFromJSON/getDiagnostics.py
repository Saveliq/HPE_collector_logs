"""Lossless diagnostic tables from collected Redfish responses.

Keep source paths: several Redfish views can describe the same physical device.
Only repeated HTTP responses to fragment links are collapsed, never devices by name.
"""

FIRMWARE_FIELDS = {"Firmware", "FirmwareVersion", "FirmwarePackageVersion",
                   "BiosVersion", "ManagerFirmwareVersion"}
STATUS_FIELDS = {"Status", "OperationalStatus", "DIMMStatus", "LinkStatus",
                 "PowerSupplyStatus", "BackupPowerSourceStatus", "StatusIndicator",
                 "AmpModeStatus", "CarrierAuthenticationStatus", "DiskDriveStatusReasons",
                 "iLOSelfTestResults"}
POWER_FIELDS = {
    "PowerRegulatorMode", "PowerProfile", "PowerMode", "WorkloadProfile",
    "PowerRestorePolicy", "PowerAutoOn", "PowerOnDelay", "PowerState",
    "HighEfficiencyMode", "BrownoutRecoveryEnabled", "PowerAllocationLimit",
    "PowerConsumedWatts", "PowerCapacityWatts", "PowerAllocatedWatts",
    "PowerAvailableWatts", "PowerRequestedWatts", "LimitInWatts",
    "LimitException", "CorrectionInMs", "PrMode", "Cap",
}
SKIP_BRANCHES = {"Links", "links", "Actions", "Members", "RelatedItem"}


def _dict(value):
    return value if isinstance(value, dict) else {}


def _oem(data):
    oem = _dict(data.get("Oem"))
    return _dict(oem.get("Hpe") or oem.get("Hp"))


def firmware_versions(value, path=""):
    """Return every version, including explicitly labelled backup versions."""
    if isinstance(value, dict):
        if "VersionString" in value:
            yield path, value["VersionString"]
        else:
            for key, child in value.items():
                if isinstance(child, (dict, list)):
                    yield from firmware_versions(child, path + "/" + key)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from firmware_versions(child, path + "/" + str(index))
    else:
        yield path, value


def component_fields(data):
    """Read this component's status, without borrowing a child's health."""
    status = _dict(data.get("Status"))
    result = {key: status.get(key) for key in ("State", "Health", "HealthRollup")}
    versions = []
    for field in ("FirmwareVersion", "Firmware", "FirmwarePackageVersion"):
        value = data.get(field)
        if isinstance(value, dict) and "Current" in value:
            value = value["Current"]
        for _, version in firmware_versions(value):
            if version is not None and str(version).strip() and version not in versions:
                versions.append(version)
    result["FirmwareVersion"] = "; ".join(str(v).strip() for v in versions) or None
    result["TemperatureCelsius"] = data.get("CurrentTemperatureCelsius", data.get("ReadingCelsius"))
    result["DIMMStatus"] = data.get("DIMMStatus", _oem(data).get("DIMMStatus"))
    return result


def canonical_resources(raw_data):
    """Prefer the base response over repeated full bodies fetched via # links."""
    resources = {}
    for source, data in sorted(raw_data.items(), key=lambda item: ("#" in item[0], item[0])):
        if not isinstance(data, dict):
            continue
        base = source.split("#", 1)[0].rstrip("/")
        body_id = (data.get("@odata.id") or "").rstrip("/")
        # A fragment request in collector output usually returns the whole parent.
        key = base if "#" in source and body_id == base else source.rstrip("/")
        resources.setdefault(key, data)
    return resources


def get_diagnostics(raw_data):
    result = {"FirmwareInventory": [], "ComponentStatus": [], "Temperatures": [], "PowerPolicy": []}

    def walk(data, source, trail="", parent_name=""):
        if isinstance(data, list):
            for index, child in enumerate(data):
                walk(child, source, trail + "/" + str(index), parent_name)
            return
        if not isinstance(data, dict):
            return
        name = data.get("Name") or data.get("DeviceLocator") or parent_name or source.rsplit("/", 1)[-1]
        location = data.get("Location") or data.get("PhysicalContext") or data.get("DeviceLocator")
        path = source + ("#" + trail if trail else "")
        identity = {"Name": name, "SerialNumber": data.get("SerialNumber"),
                    "Location": location, "SourcePath": path}
        for field in sorted(FIRMWARE_FIELDS):
            if field in data:
                for suffix, version in firmware_versions(data[field]):
                    result["FirmwareInventory"].append(dict(identity, Field=field + suffix, Version=version))
        # Standard SoftwareInventory resources use Version, rather than FirmwareVersion.
        if "FirmwareInventory/" in source and "Version" in data:
            result["FirmwareInventory"].append(dict(identity, Field="Version", Version=data["Version"]))

        for field in sorted(STATUS_FIELDS):
            if field not in data:
                continue
            value = data[field]
            status = _dict(value)
            result["ComponentStatus"].append(dict(
                identity, Field=field, State=status.get("State"), Health=status.get("Health"),
                HealthRollup=status.get("HealthRollup"),
                Details=value if not status else {k: v for k, v in status.items()
                                                 if k not in ("State", "Health", "HealthRollup")},
            ))

        for field in ("ReadingCelsius", "CurrentTemperatureCelsius", "MaximumTemperatureCelsius"):
            if field in data:
                status = _dict(data.get("Status"))
                result["Temperatures"].append(dict(
                    identity, Field=field, ReadingCelsius=data[field],
                    UpperThresholdNonCritical=data.get("UpperThresholdNonCritical"),
                    UpperThresholdCritical=data.get("UpperThresholdCritical"),
                    UpperThresholdFatal=data.get("UpperThresholdFatal"),
                    State=status.get("State"), Health=status.get("Health"),
                ))
        for field in sorted(POWER_FIELDS):
            if field in data and not isinstance(data[field], (dict, list)):
                result["PowerPolicy"].append(dict(identity, Field=field, Value=data[field]))

        for key, child in data.items():
            if key.startswith("@") or key in SKIP_BRANCHES | FIRMWARE_FIELDS | STATUS_FIELDS:
                continue
            if isinstance(child, (dict, list)):
                child_name = name if isinstance(child, list) else name + " / " + key
                walk(child, source, trail + "/" + key, child_name)

    for source, data in canonical_resources(raw_data).items():
        # Pending settings and event history are not current component telemetry.
        if any(part.lower() in {"settings", "entries", "biosregistries"} for part in source.split("/")):
            continue
        walk(data, source)
    return result
