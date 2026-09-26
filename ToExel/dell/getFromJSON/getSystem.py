from search import SYSTEM, Resources, _dict, _list, _first, is_absent, stripJSON


def get_system(json_data):
    resources = Resources(json_data)
    system = resources.data.get(SYSTEM, {})
    attributes = _dict(resources.data.get(SYSTEM + "/Bios", {}).get("Attributes"))
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
        "ProcessorModel": processor_summary.get("Model"),
        "ProcessorCount": processor_summary.get("Count"),
        "TotalSystemMemoryGiB": memory_summary.get("TotalSystemMemoryGiB"),
        "MemorySummary": _dict(memory_summary.get("Status")).get("HealthRollup"),
    }
    # Dell reports a Disabled TrustedModules placeholder even with no TPM fitted.
    if str(attributes.get("TpmInfo", "")).strip().lower() != "no tpm present":
        modules = [module for module in _list(system.get("TrustedModules"))
                   if isinstance(module, dict) and module.get("InterfaceType") and not is_absent(module)]
        if modules:
            result["TrustedModules"] = modules
    return stripJSON(result)
