from search import SYSTEM, MANAGER, Resources, _dict, _list, _first, is_absent, stripJSON


def _trusted_modules(system, attributes):
    """Return installed TPM/trusted-module records with status fields preserved."""
    # Dell exposes a Disabled placeholder in TrustedModules even when BIOS says
    # that no TPM is installed. In that case the placeholder must not become an
    # inventory row.
    if str(attributes.get("TpmInfo", "")).strip().lower() == "no tpm present":
        return []

    result = []
    for index, module in enumerate(_list(system.get("TrustedModules"))):
        if not isinstance(module, dict) or is_absent(module):
            continue
        # A real module may have InterfaceType but no independent S/N/P/N.
        # Preserve the standard Status object as flat telemetry for the Excel
        # writer instead of replacing the whole array by one generic row.
        status = _dict(module.get("Status"))
        normalized = dict(module)
        normalized.update({
            "Name": module.get("InterfaceType") or "TrustedModule",
            "State": status.get("State"),
            "Health": status.get("Health"),
            "HealthRollup": status.get("HealthRollup"),
            "SourcePath": f"{SYSTEM}#/TrustedModules/{index}",
        })
        result.append(normalized)
    return result


def get_system(json_data):
    resources = Resources(json_data)
    system = resources.data.get(SYSTEM, {})
    attributes = _dict(resources.data.get(SYSTEM + "/Bios", {}).get("Attributes"))
    power_attributes = _dict(resources.data.get(
        MANAGER + "/Oem/Dell/DellAttributes/System.Embedded.1", {}).get("Attributes"))
    status = _dict(system.get("Status"))
    processor_summary = _dict(system.get("ProcessorSummary"))
    memory_summary = _dict(system.get("MemorySummary"))
    result = {
        "BiosVersion": _first(system.get("BiosVersion"), attributes.get("SystemBiosVersion")),
        "ServerState": status.get("State"),
        "ServerHealth": status.get("Health"),
        "ServerHealthRollup": status.get("HealthRollup"),
        "PowerState": system.get("PowerState"),
        "PowerRegulatorMode": _first(attributes.get("SysProfile"), attributes.get("ProcPwrPerf")),
        "PowerAutoOn": _first(attributes.get("AcPwrRcvry"), system.get("PowerRestorePolicy")),
        "RedundancyPolicy": power_attributes.get("ServerPwr.1.PSRedPolicy"),
        "HotSpare": power_attributes.get("ServerPwr.1.PSRapidOn"),
        "PrimaryPSU": power_attributes.get("ServerPwr.1.RapidOnPrimaryPSU"),
        "ProcessorModel": processor_summary.get("Model"),
        "ProcessorCount": processor_summary.get("Count"),
        "TotalSystemMemoryGiB": memory_summary.get("TotalSystemMemoryGiB"),
        "MemorySummary": _dict(memory_summary.get("Status")).get("HealthRollup"),
    }
    modules = _trusted_modules(system, attributes)
    if modules:
        result["TrustedModules"] = modules
    return stripJSON(result)
