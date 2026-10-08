"""Huawei Systems/{id}: model, BIOS, state, CPU and RAM summaries."""
from ._common import parsed


def get_system(json_data):
    s=parsed(json_data)
    return {
        'Model': s['Model'], 'PartNumber': s['PartNumber'],
        'SerialNumber': s['SerialNumber'], 'BiosVersion': s['BiosVersion'],
        'BiosSource': s['BiosSource'], 'ServerState': s['ServerState'],
        'ServerHealth': s['ServerHealth'], 'ServerHealthRollup': s['ServerHealthRollup'],
        'PowerState': s['PowerState'], 'ProcessorModel': s['ProcessorModel'],
        'ProcessorCount': s['ProcessorCount'], 'TotalSystemMemoryGiB': s['MemoryTotalGiB'],
        'MemorySummary': s['MemoryHealth'], 'SourcePath': s['SystemPath'],
        'PowerConsumedWatts': s['PowerConsumedWatts'], 'RedundancyMode': s['RedundancyMode'],
        'CustomPowerPolicy': s['CustomPowerPolicy'], 'PowerSaving': s['PowerSaving'],
        'PSUModes': s['PSUModes'], 'RedundancyGroups': s['RedundancyGroups'],
    }
