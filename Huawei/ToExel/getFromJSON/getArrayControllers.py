"""Storage: embedded Storages/StorageControllers and Chassis/Drives.

Return (controllers, disks) as in the original toExel interface.
Missing drive P/N is intentionally None (not the model).
"""
from ._common import components, parsed, descendants, is_absent, obj


def get_array_controllers(json_data):
    controllers=components(json_data,'RAID/HBA')
    disks=components(json_data,'Диск')
    for c in controllers:
        c['ComponentName']=('HBA контроллер' if 'hba' in str(c.get('Model') or '').lower()
                            else 'RAID контроллер' if 'raid' in str(c.get('Model') or '').lower()
                            else 'Контроллер хранения')
    for d in disks:
        d['InterfaceType']=d.get('Protocol')
        speed=d.get('NegotiatedSpeedGbs')
        d['InterfaceSpeedMbps']=(speed*1000 if isinstance(speed,(int,float)) else None)
    return controllers,disks


def get_storage_enclosures(json_data):
    # There is no invented enclosure entry when no physical resource was collected.
    s=parsed(json_data); ch=s['ChassisPath']
    if not ch:return []
    return [dict(b,SourcePath=p) for p,b in descendants(json_data,ch+'/Enclosures')
            if not is_absent(b)]
