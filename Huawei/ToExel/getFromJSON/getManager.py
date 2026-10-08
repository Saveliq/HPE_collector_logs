"""Huawei iBMC FirmwareVersion, with ActiveBMC fallback; never BackupBMC."""
from ._common import parsed


def get_manager(json_data):
    s=parsed(json_data)
    return {'iBMCVersion':s['iBMCVersion'], 'FirmwareVersion':s['iBMCVersion'],
            'FirmwareSource':s['iBMCSource'], 'SourcePath':s['ManagerPath']}
