from search import Resources, first_value, huawei, identifier


def get_memory(json_data):
    resources = Resources(json_data)
    modules = resources.installed(resources.children(resources.system_path, "Memory"))
    for module in modules:
        oem = huawei(module)
        module.update(
            PartNumber=identifier(module.get("PartNumber"), oem.get("OriginalPartNumber")),
            SizeMB=module.get("CapacityMiB"), Frequency=module.get("OperatingSpeedMhz"),
            Rank=module.get("RankCount"), Technology=first_value(module.get("MemoryDeviceType"), oem.get("Type")),
            DIMMStatus=first_value(module.get("DIMMStatus"), module.get("Health"),
                                   module.get("HealthRollup"), module.get("State")),
            FirmwareVersion=first_value(module.get("FirmwareVersion"), module.get("FirmwareRevision")),
        )
    return modules
