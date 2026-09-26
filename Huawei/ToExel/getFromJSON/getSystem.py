from search import Resources, as_dict, as_list, huawei, first_value, is_absent


def get_system(json_data):
    resources = Resources(json_data)
    system = resources.resolve(resources.system_path)
    status = as_dict(system.get("Status"))
    oem = huawei(system)
    attributes = as_dict(resources.resolve(resources.system_path + "/Bios").get("Attributes"))
    processors = as_dict(system.get("ProcessorSummary"))
    memory = as_dict(system.get("MemorySummary"))
    result = {
        "BiosVersion": system.get("BiosVersion"),
        "ServerState": status.get("State"), "ServerHealth": status.get("Health"),
        "ServerHealthRollup": status.get("HealthRollup"), "PowerState": system.get("PowerState"),
        "PowerRegulatorMode": first_value(attributes.get("CustomPowerPolicy"), oem.get("PowerPolicy")),
        "PowerAutoOn": first_value(oem.get("PowerOnStrategy"), system.get("PowerRestorePolicy")),
        "ProcessorModel": processors.get("Model"), "ProcessorCount": processors.get("Count"),
        "TotalSystemMemoryGiB": memory.get("TotalSystemMemoryGiB"),
        "MemorySummary": as_dict(memory.get("Status")).get("HealthRollup"),
    }
    modules = [module for module in as_list(system.get("TrustedModules"))
               if isinstance(module, dict) and not is_absent(module) and
               (module.get("InterfaceType") or module.get("Status"))]
    if modules:
        result["TrustedModules"] = modules
    return result
