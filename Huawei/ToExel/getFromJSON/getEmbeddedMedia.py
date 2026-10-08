"""Huawei Systems/Managers USBDevices inventory, only if present in collected JSON."""
from ._common import parsed, descendants, is_absent


def get_embedded_media(json_data):
    s=parsed(json_data);out=[]
    for base in (s['SystemPath'],s['ManagerPath']):
        if base:
            for p,b in descendants(json_data,base+'/USBDevices'):
                if not is_absent(b):out.append(dict(b, SourcePath=p))
    return {'USBDevices':out}
