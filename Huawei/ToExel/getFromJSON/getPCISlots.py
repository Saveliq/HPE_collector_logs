"""Physical PCIe slot status, if the collector captured Chassis/PCIeSlots."""
from ._common import parsed, obj, arr


def get_PCI_slots(json_data):
    s=parsed(json_data);ch=s['ChassisPath']
    if not ch:return {}
    slots=obj(json_data.get(ch+'/PCIeSlots'))
    result={}
    for i,slot in enumerate(arr(slots.get('Slots')),1):
        if isinstance(slot,dict):
            result['NetworkAdapter_'+str(i)]={
                'Name':slot.get('Name') or slot.get('SlotType'),
                'Status':obj(slot.get('Status')).get('State'),
                'SourcePath':ch+f'/PCIeSlots#/Slots/{i-1}'
            }
    return result
