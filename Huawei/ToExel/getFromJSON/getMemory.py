"""DIMM inventory with original P/N, OEM OriginalPartNumber fallback and MiB units."""
from ._common import components


def get_memory(json_data):
    memory=components(json_data, 'Память')
    for module in memory:
        module['SizeMiB']=module.get('CapacityMiB')
        module['Frequency']=module.get('OperatingSpeedMhz')
        module['Rank']=module.get('RankCount')
        module['Technology']=module.get('MemoryDeviceType')
        module['DIMMStatus']=(module.get('DIMMStatus') or module.get('HealthRollup')
                              or module.get('Health') or module.get('State'))
    return memory
