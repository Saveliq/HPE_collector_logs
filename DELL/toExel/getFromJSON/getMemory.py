import re

from search import SYSTEM, Resources, _installed, _first, stripJSON


def get_memory(json_data):
    resources = Resources(json_data)
    memory = _installed(resources, resources.matching(re.escape(SYSTEM) + r"/Memory/[^/]+"))
    for module in memory:
        oem = resources.oem(module, "DellMemory")
        module.update(SizeMB=module.get("CapacityMiB"), Frequency=module.get("OperatingSpeedMhz"),
                      Rank=module.get("RankCount"), Technology=module.get("MemoryDeviceType"),
                      DIMMStatus=_first(module.get("DIMMStatus"), oem.get("DIMMStatus"),
                                        module.get("Health"), module.get("HealthRollup"), module.get("State")))
    return stripJSON(memory)
