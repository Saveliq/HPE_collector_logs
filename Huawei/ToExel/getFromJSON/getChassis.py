"""Huawei Chassis: physical system identifiers; installed fan inventory if available."""
from ._common import parsed, descendants, is_absent, obj, arr


def get_chassis(json_data):
    s=parsed(json_data)
    ch=s['ChassisPath']; fans=[]
    if ch:
        therm=obj(json_data.get(ch+'/Thermal'))
        for i, fan in enumerate(arr(therm.get('Fans'))):
            if isinstance(fan,dict) and not is_absent(fan):
                fans.append(dict(fan,SourcePath=ch+f'/Thermal#/Fans/{i}'))
        for p,b in descendants(json_data,ch+'/ThermalSubsystem/Fans'):
            if not is_absent(b): fans.append(dict(b, SourcePath=p))
    return {
        'Model':s['Model'], 'PartNumber':s['PartNumber'], 'SKU':s['PartNumber'],
        'SerialNumber':s['SerialNumber'], 'ServiceTag':None,
        'Fans':fans, 'StorageBatteries':[], 'SourcePath':ch
    }
