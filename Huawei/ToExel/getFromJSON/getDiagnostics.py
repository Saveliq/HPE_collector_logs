"""Diagnostics and firmware inventory based on Huawei/xFusion captured responses.

Records keep exact URLs. Backup images are separate firmware records, not hardware.
"""
from ._common import parsed, obj, oem


def firmware_versions(value, path=''):
    if isinstance(value,dict):
        if 'VersionString' in value:
            yield path, value['VersionString']
        else:
            for key,child in value.items():
                yield from firmware_versions(child, path+'/'+str(key))
    elif isinstance(value,list):
        for i,child in enumerate(value):
            yield from firmware_versions(child,path+'/'+str(i))
    elif value is not None:
        yield path,value


def component_fields(data):
    st=obj(obj(data).get('Status'))
    versions=[]
    for key in ('FirmwareVersion','FirmwareRevision','FirmwarePackageVersion','Revision','Firmware'):
        v=obj(data).get(key)
        if isinstance(v,dict) and 'Current' in v:v=v['Current']
        for _,value in firmware_versions(v):
            if value is not None and str(value).strip() and value not in versions:
                versions.append(value)
    vendor=oem(data)
    return {'State':st.get('State'),'Health':st.get('Health'), 'HealthRollup':st.get('HealthRollup'),
            'FirmwareVersion':'; '.join(map(str,versions)) or None,
            'TemperatureCelsius':obj(data).get('CurrentTemperatureCelsius',obj(data).get('ReadingCelsius')),
            'DIMMStatus':obj(data).get('DIMMStatus') or vendor.get('DIMMStatus')}


def canonical_resources(raw_data):
    canonical={}
    for url,body in sorted(raw_data.items(),key=lambda x: ('#' in x[0],x[0])):
        if not isinstance(body,dict):continue
        root=url.split('#',1)[0].rstrip('/')
        idpath=str(body.get('@odata.id') or '').rstrip('/')
        key=(root if '#' in url and idpath==root else url.rstrip('/'))
        if idpath and raw_data.get(idpath)==body:key=idpath
        canonical.setdefault(key,body)
    return canonical


def get_diagnostics(json_data):
    s=parsed(json_data)
    result={'FirmwareInventory':[], 'ComponentStatus':[], 'Temperatures':[], 'PowerPolicy':[]}
    for fw in s['FirmwareInventory']:
        result['FirmwareInventory'].append({
            'SourcePath':fw['SourcePath'], 'Field':'Version','Version':fw['Version'],
            'Name':fw['Name'],'FirmwareRole':fw['Role'],'State':fw['State'],'Health':fw['Health']})
    for component in s['Components']:
        identity={k:component.get(k) for k in ('Name','Model','PartNumber','SerialNumber','SourcePath')}
        identity['ComponentPath']=component['SourcePath']
        if component.get('FirmwareVersion') is not None:
            result['FirmwareInventory'].append(dict(identity,Field='FirmwareVersion',Version=component['FirmwareVersion']))
        if component.get('State') is not None or component.get('Health') is not None or component.get('HealthRollup') is not None:
            result['ComponentStatus'].append(dict(identity,Field='Status',State=component.get('State'),
                Health=component.get('Health'),HealthRollup=component.get('HealthRollup')))
        for key in ('TemperatureCelsius','LifeLeftPercent'):
            value=(component.get('Info') or {}).get(key)
            if value is not None and key=='TemperatureCelsius':
                result['Temperatures'].append(dict(identity,Field=key,Value=value))
    if s['PowerConsumedWatts'] is not None:
        result['PowerPolicy'].append({'SourcePath':s['PowerConsumedSource'],
                                     'Field':'PowerConsumedWatts','Value':s['PowerConsumedWatts']})
    if s['RedundancyMode'] is not None:
        result['PowerPolicy'].append({'SourcePath':s['ChassisPath']+'/Power',
                                     'Field':'Redundancy.Mode','Value':s['RedundancyMode']})
    return result
