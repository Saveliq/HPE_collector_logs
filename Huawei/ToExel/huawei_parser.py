"""Huawei / xFusion Redfish dump parser.

Resource paths are discovered from collection references, rather than assuming
Dell's System.Embedded.1/iDRAC paths. Every component retains a precise JSON
source pointer and provenance for individual field fallbacks. Nothing is
silently synthesized as a hardware serial number or part number.
"""
from __future__ import annotations

from collections import defaultdict
import json
from pathlib import Path
import re

MISSING = {"", "none", "null", "n/a", "na", "unknown", "notavailable", "not available", "--", "-"}
ABSENT = {"absent", "notpresent", "notinstalled", "empty", "removed"}


def obj(v): return v if isinstance(v, dict) else {}
def arr(v): return v if isinstance(v, list) else []
def oem(v):
    d = obj(obj(v).get('Oem'))
    return obj(d.get('Huawei') or d.get('xFusion') or d.get('XFUSION') or d.get('FusionServer'))

def valid(v):
    if v is None or isinstance(v, (dict, list)) or (isinstance(v, str) and v.strip().lower() in MISSING):
        return False
    return True

def pick(*candidates):
    """Candidates are (value, exact original JSON field path). Preserve 0 and False."""
    for value, source in candidates:
        if valid(value): return value, source
    return None, ''

def status(v):
    d = obj(obj(v).get('Status'))
    return {'State': d.get('State'), 'Health': d.get('Health'), 'HealthRollup': d.get('HealthRollup')}

def is_absent(v):
    return str(status(v)['State'] or '').replace('_','').replace(' ','').lower() in ABSENT or str(obj(v).get('Presence','')).lower() in ABSENT

def nested(v, *keys):
    for k in keys: v = obj(v).get(k)
    return v

def path_field(path, field): return f'{path}#{field}'


def collection_base(d, plural):
    root = f'/redfish/v1/{plural}'
    refs = arr(obj(d.get(root)).get('Members'))
    for ref in refs:
        p = obj(ref).get('@odata.id')
        if isinstance(p, str) and isinstance(d.get(p.rstrip('/')), dict):
            return p.rstrip('/')
    paths = sorted(p for p in d if re.fullmatch(re.escape(root)+r'/[^/]+',p) and isinstance(d[p], dict) and 'error' not in d[p])
    return paths[0] if paths else None


def descendants(d, parent, *, depth=1):
    if not parent:return []
    # Explicit link resources trump auxiliary sub-resources.
    prefix = parent.rstrip('/')+'/'
    paths = sorted(p for p,v in d.items() if p.startswith(prefix) and p[len(prefix):].count('/') == depth - 1 and isinstance(v,dict) and 'error' not in v and not '#' in p)
    return [(p,d[p]) for p in paths]


def component(kind, path, body, *, name=None, model=None, part=None, part_src=None, serial=None, serial_src=None, fw=None, fw_src=None, extras=None):
    b = obj(body); vendor = oem(b)
    pn, pnsource = pick((part, part_src or ''), (b.get('PartNumber'),path_field(path,'/PartNumber')),
                        (vendor.get('PartNumber'),path_field(path,'/Oem/*/PartNumber')))
    sn, snsource = pick((serial, serial_src or ''), (b.get('SerialNumber'),path_field(path,'/SerialNumber')),
                        (vendor.get('SerialNumber'),path_field(path,'/Oem/*/SerialNumber')))
    version, version_src = pick((fw,fw_src or ''),(b.get('FirmwareVersion'),path_field(path,'/FirmwareVersion')),
                                (b.get('FirmwareRevision'),path_field(path,'/FirmwareRevision')),
                                (b.get('Revision'),path_field(path,'/Revision')))
    stat = status(b)
    return {'Category':kind,'Name':name or b.get('Name') or b.get('DeviceLocator') or b.get('Id') or kind,
            'Model':model or b.get('Model') or b.get('ProductName') or '',
            'PartNumber':pn,'SerialNumber':sn,'FirmwareVersion':version,
            'State':stat['State'],'Health':stat['Health'],'HealthRollup':stat['HealthRollup'],
            'Manufacturer':b.get('Manufacturer'), 'Location':b.get('DeviceLocator') or vendor.get('DeviceLocator') or '',
            'SourcePath':path, 'PartNumberSource':pnsource,'SerialNumberSource':snsource,'FirmwareSource':version_src,
            'Info': extras or {}}


def parse_huawei(raw, source_file=''):
    if not isinstance(raw,dict):return None
    sys_path = collection_base(raw,'Systems'); ch_path=collection_base(raw,'Chassis'); mgr_path=collection_base(raw,'Managers')
    if not sys_path:return None
    s=obj(raw.get(sys_path)); ch=obj(raw.get(ch_path));mgr=obj(raw.get(mgr_path))
    if not (valid(s.get('SerialNumber')) or valid(s.get('Model'))):return None
    bios=obj(raw.get(sys_path+'/Bios')); fw_base='/redfish/v1/UpdateService/FirmwareInventory'
    firmwares=descendants(raw,fw_base)
    firmware_by_id={p.rsplit('/',1)[-1].lower():(p,b) for p,b in firmwares}
    sbios=(firmware_by_id.get('bios') or (None,{}))
    s_bios=pick((s.get('BiosVersion'),path_field(sys_path,'/BiosVersion')),
                (obj(bios.get('Attributes')).get('SystemBiosVersion'),path_field(sys_path+'/Bios','/Attributes/SystemBiosVersion')),
                (sbios[1].get('Version'),path_field(sbios[0],'/Version') if sbios[0] else ''))
    bm = firmware_by_id.get('activebmc') or (None,{})
    bmc=pick((mgr.get('FirmwareVersion'),path_field(mgr_path,'/FirmwareVersion')),
             (bm[1].get('Version'),path_field(bm[0],'/Version') if bm[0] else ''))
    pwr_path=(ch_path+'/Power') if ch_path else None;pwr=obj(raw.get(pwr_path))
    power_control=arr(pwr.get('PowerControl'))
    consumption=pick(*[(x.get('PowerConsumedWatts'),path_field(pwr_path,f'/PowerControl/{i}/PowerConsumedWatts')) for i,x in enumerate(power_control) if isinstance(x,dict)])
    # Power capping is an activation flag, independent of the configured limit.
    # Preserve False as a meaningful observed value and do not invent False
    # when the Redfish property is absent.
    cap_candidates = []
    limit_candidates = []
    expected_candidates = []
    for i, control in enumerate(power_control):
        if not isinstance(control, dict):
            continue
        extended = obj(oem(control).get('PowerMetricsExtended'))
        cap_candidates.append((extended.get('PowerLimitActivated'),
                               path_field(pwr_path, f'/PowerControl/{i}/Oem/*/PowerMetricsExtended/PowerLimitActivated')))
        limit_candidates.append((obj(control.get('PowerLimit')).get('LimitInWatts'),
                                 path_field(pwr_path, f'/PowerControl/{i}/PowerLimit/LimitInWatts')))
        expected_candidates.append((obj(oem(control).get('ExpectedRedundancy')).get('@odata.id'),
                                    path_field(pwr_path, f'/PowerControl/{i}/Oem/*/ExpectedRedundancy/@odata.id')))
    cap_activated = pick(*cap_candidates)
    cap_limit = pick(*limit_candidates)
    expected_redundancy = pick(*expected_candidates)
    red=arr(pwr.get('Redundancy'))
    red_modes='; '.join(f'{r.get("Name") or r.get("MemberId")}: {r.get("Mode")}' for r in red if isinstance(r,dict) and valid(r.get('Mode')))
    # These are BIOS settings, NOT fields from Chassis/Power.
    bios_attrs=obj(bios.get('Attributes'))
    power_policy=pick((bios_attrs.get('CustomPowerPolicy'),path_field(sys_path+'/Bios','/Attributes/CustomPowerPolicy')))
    power_saving=pick((bios_attrs.get('PowerSaving'),path_field(sys_path+'/Bios','/Attributes/PowerSaving')))
    # ActiveStandby is *per PSU*.  Two Active PSUs must not be reinterpreted as
    # "Active/Standby" or "Load Balancing" without the corresponding policy.
    psu_modes=[]
    for i,psu in enumerate(arr(pwr.get('PowerSupplies'))):
        if not isinstance(psu,dict) or is_absent(psu):continue
        mode=oem(psu).get('ActiveStandby')
        if valid(mode):
            psu_modes.append({'Name':psu.get('Name') or f'PSU{i+1}', 'Mode':mode,
                              'Source':path_field(pwr_path,f'/PowerSupplies/{i}/Oem/*/ActiveStandby')})
    # Huawei/xFusion can expose BOTH Sharing and Failover groups for the same
    # pair of PSUs.  List them separately, reporting missing Health honestly.
    redundancy_groups=[]
    for i,group in enumerate(red):
        if not isinstance(group,dict):continue
        mode=group.get('Mode')
        if not valid(mode):continue
        st=obj(group.get('Status'))
        redundancy_groups.append({'Mode':mode,'Health':st.get('Health'),
                                  'Enabled':group.get('RedundancyEnabled'),
                                  'EnabledSource':path_field(pwr_path, f'/Redundancy/{i}/RedundancyEnabled')
                                                   if 'RedundancyEnabled' in group else '',
                                  'Source':path_field(pwr_path,f'/Redundancy/{i}')})
    # Resolve ExpectedRedundancy only when the @odata.id belongs to an actual
    # member of the reported redundancy array; retain the raw reference too.
    expected_mode = None
    expected_ref = expected_redundancy[0]
    if isinstance(expected_ref, str):
        for i, group in enumerate(red):
            if isinstance(group, dict) and group.get('@odata.id') == expected_ref:
                expected_mode = group.get('Mode') if valid(group.get('Mode')) else None
                break
    memsum=obj(s.get('MemorySummary')); cpusum=obj(s.get('ProcessorSummary'))
    part=pick((s.get('PartNumber'),path_field(sys_path,'/PartNumber')),(ch.get('PartNumber'),path_field(ch_path,'/PartNumber')),
              (s.get('SKU'),path_field(sys_path,'/SKU')))
    serial=pick((s.get('SerialNumber'),path_field(sys_path,'/SerialNumber')),(ch.get('SerialNumber'),path_field(ch_path,'/SerialNumber')))
    result={'SourceFile':str(source_file),'SystemPath':sys_path,'ChassisPath':ch_path,'ManagerPath':mgr_path,
            'Model':pick((s.get('Model'),path_field(sys_path,'/Model')),(ch.get('Model'),path_field(ch_path,'/Model')))[0],
            'PartNumber':part[0],'PartNumberSource':part[1], 'SerialNumber':serial[0],'SerialNumberSource':serial[1],
            'BiosVersion':s_bios[0],'BiosSource':s_bios[1], 'iBMCVersion':bmc[0],'iBMCSource':bmc[1],
            'ServerState':status(s)['State'],'ServerHealth':status(s)['Health'],
            'ServerHealthRollup':status(s)['HealthRollup'], 'PowerState':s.get('PowerState'),
            'MemoryTotalGiB':pick((memsum.get('TotalSystemMemoryGiB'),path_field(sys_path,'/MemorySummary/TotalSystemMemoryGiB')),
                                  (memsum.get('TotalSystemMemoryMiB')/1024 if isinstance(memsum.get('TotalSystemMemoryMiB'),(int,float)) else None,path_field(sys_path,'/MemorySummary/TotalSystemMemoryMiB')))[0],
            'MemoryHealth':obj(memsum.get('Status')).get('HealthRollup') or obj(memsum.get('Status')).get('Health'),
            'ProcessorCount':cpusum.get('Count'),'ProcessorModel':cpusum.get('Model'),
            'PowerConsumedWatts':consumption[0],'PowerConsumedSource':consumption[1],
            'CustomPowerPolicy':power_policy[0],'CustomPowerPolicySource':power_policy[1],
            'PowerSaving':power_saving[0],'PowerSavingSource':power_saving[1],
            'PSUModes':psu_modes,'RedundancyGroups':redundancy_groups,
            'PowerCappingActivated':cap_activated[0], 'PowerCappingSource':cap_activated[1],
            'PowerCappingLimitWatts':cap_limit[0], 'PowerCappingLimitSource':cap_limit[1],
            'ExpectedRedundancy':expected_ref, 'ExpectedRedundancyMode':expected_mode,
            'ExpectedRedundancySource':expected_redundancy[1],
            'RedundancyMode':red_modes or None,'Components':[],'FirmwareInventory':[], 'Redundancy':red,
            'Raw':raw}
    cs=result['Components']
    # CPUs: Huawei/xFusion part and serial are generally OEM-only.
    for p,b in descendants(raw,sys_path+'/Processors'):
        if is_absent(b):continue
        vendor=oem(b)
        cs.append(component('Процессор',p,b,
            part=vendor.get('PartNumber'),part_src=path_field(p,'/Oem/*/PartNumber'),
            serial=vendor.get('SerialNumber'),serial_src=path_field(p,'/Oem/*/SerialNumber'),
            extras={'Cores':b.get('TotalCores'),'Threads':b.get('TotalThreads'),'Socket':b.get('Socket'),'TemperatureCelsius':vendor.get('Temperature')}))
    for p,b in descendants(raw,sys_path+'/Memory'):
        if is_absent(b) or (b.get('CapacityMiB') == 0 and not valid(b.get('PartNumber'))):continue
        vendor=oem(b)
        cs.append(component('Память',p,b,name=b.get('DeviceLocator') or b.get('Name'),
            part=pick((b.get('PartNumber'),path_field(p,'/PartNumber')),
                      (vendor.get('OriginalPartNumber'),path_field(p,'/Oem/*/OriginalPartNumber')))[0],
            part_src=pick((b.get('PartNumber'),path_field(p,'/PartNumber')),
                      (vendor.get('OriginalPartNumber'),path_field(p,'/Oem/*/OriginalPartNumber')))[1],
            fw=b.get('FirmwareRevision'),fw_src=path_field(p,'/FirmwareRevision'),
            extras={'CapacityGiB':b.get('CapacityMiB')/1024 if isinstance(b.get('CapacityMiB'),(int,float)) else None,
                    'SpeedMHz':b.get('OperatingSpeedMhz'),'OEM_BOM':vendor.get('BomNumber'),'Type':b.get('MemoryDeviceType')}))
    # RAID: controllers are inline StorageControllers[] instead of addressable resources.
    for sp,storage in descendants(raw,sys_path+'/Storages'):
        for i,ctrl in enumerate(arr(storage.get('StorageControllers'))):
            if not isinstance(ctrl,dict) or is_absent(ctrl):continue
            ctrl_path=sp+f'#/StorageControllers/{i}'
            vendor=oem(ctrl)
            cs.append(component('RAID/HBA',ctrl_path,ctrl,
                part=pick((ctrl.get('PartNumber'),path_field(ctrl_path,'/PartNumber')),
                          (vendor.get('PartNumber'),path_field(ctrl_path,'/Oem/*/PartNumber')),
                          (vendor.get('ControllerPartNumber'),path_field(ctrl_path,'/Oem/*/ControllerPartNumber')))[0],
                part_src=pick((ctrl.get('PartNumber'),path_field(ctrl_path,'/PartNumber')),
                          (vendor.get('PartNumber'),path_field(ctrl_path,'/Oem/*/PartNumber')),
                          (vendor.get('ControllerPartNumber'),path_field(ctrl_path,'/Oem/*/ControllerPartNumber')))[1],
                extras={'StorageId':storage.get('Id'),'SupportedRAIDTypes':ctrl.get('SupportedRAIDTypes'),
                        'SpeedGbps':ctrl.get('SpeedGbps')}))
    # Drive responses are authoritative. Storage.Drives holds lightweight link stubs.
    drive_paths=set()
    for p,b in descendants(raw,ch_path+'/Drives'):
        if is_absent(b):continue
        drive_paths.add(p)
        vendor=oem(b)
        cs.append(component('Диск',p,b,fw=b.get('Revision'),fw_src=path_field(p,'/Revision'),
            extras={'CapacityGB':round(b['CapacityBytes']/10**9,3) if isinstance(b.get('CapacityBytes'),(int,float)) else None,
                    'MediaType':b.get('MediaType'),'Protocol':b.get('Protocol'),
                    'SpeedGbps':b.get('NegotiatedSpeedGbs'),'LifeLeftPercent':b.get('PredictedMediaLifeLeftPercent'),
                    'FirmwareStatus':vendor.get('FirmwareStatus'),'TemperatureCelsius':vendor.get('TemperatureCelsius'),
                    'FailurePredicted':b.get('FailurePredicted')}))
    # Some generations place complete Drive resources elsewhere. Link refs avoid duplicate copies.
    for sp,storage in descendants(raw,sys_path+'/Storages'):
        for i,dr in enumerate(arr(storage.get('Drives'))):
            if not isinstance(dr,dict):continue
            ref=dr.get('@odata.id');full=obj(raw.get(ref))
            if ref in drive_paths or (not full and len(dr)<=4):continue
            b=full or dr;p=ref or sp+f'#/Drives/{i}'
            if not is_absent(b):cs.append(component('Диск',p,b))
            drive_paths.add(p)
    # PSU and Redundancy are embedded inline in /Chassis/<id>/Power.
    for i,b in enumerate(arr(pwr.get('PowerSupplies'))):
        if not isinstance(b,dict) or is_absent(b):continue
        p=pwr_path+f'#/PowerSupplies/{i}'
        cs.append(component('Блок питания',p,b,extras={
            'CapacityWatts':b.get('PowerCapacityWatts'),'ActiveStandby':oem(b).get('ActiveStandby'),
            'PowerInputWatts':oem(b).get('PowerInputWatts'),'PowerOutputWatts':oem(b).get('PowerOutputWatts')}))
    # Inventory cards: prefer Chassis NetworkAdapters and link only to a PCIe card
    # with a *unique* matching location / slot, never match globally by model alone.
    pci=descendants(raw,ch_path+'/PCIeDevices'); pci_used=set()
    boards=descendants(raw,ch_path+'/Boards'); board_used=set()
    for p,b in descendants(raw,ch_path+'/NetworkAdapters'):
        if is_absent(b):continue
        v=oem(b); loc=str(v.get('DeviceLocator') or '').strip().lower()
        slot=v.get('SlotNumber'); pos=str(v.get('Position') or '').strip().lower()
        matches=[(pp,x) for pp,x in pci if (str(oem(x).get('DeviceLocator') or '').strip().lower()==loc and loc)
                     or (slot is not None and oem(x).get('SlotNumber')==slot and
                         str(oem(x).get('Position') or '').lower()==pos and pos)]
        chosen=matches[0] if len(matches)==1 else (None,{})
        if chosen[0]:pci_used.add(chosen[0])
        # Mainboard/LOM boards can be matched by exact Id or DeviceLocator.
        boardmatches=[(pp,x) for pp,x in boards if (str(x.get('Id') or '')==str(b.get('Id') or '')
                       or (loc and str(x.get('DeviceLocator') or '').lower()==loc))]
        boardmatch=boardmatches[0] if len(boardmatches)==1 else (None,{})
        if boardmatch[0]:board_used.add(boardmatch[0])
        pn_candidates=[(b.get('PartNumber'),path_field(p,'/PartNumber')),
            (chosen[1].get('PartNumber'),path_field(chosen[0],'/PartNumber') if chosen[0] else ''),
            (boardmatch[1].get('PartNumber'),path_field(boardmatch[0],'/PartNumber') if boardmatch[0] else '')]
        sn_candidates=[(b.get('SerialNumber'),path_field(p,'/SerialNumber')),
            (chosen[1].get('SerialNumber'),path_field(chosen[0],'/SerialNumber') if chosen[0] else ''),
            (boardmatch[1].get('SerialNumber'),path_field(boardmatch[0],'/SerialNumber') if boardmatch[0] else '')]
        pn=pick(*pn_candidates);sn=pick(*sn_candidates)
        ports=descendants(raw,p+'/NetworkPorts')
        fw_value, fw_source = pick(
            (b.get('FirmwareVersion'),path_field(p,'/FirmwareVersion')),
            (chosen[1].get('FirmwareVersion'),path_field(chosen[0],'/FirmwareVersion') if chosen[0] else ''),
            *[(obj(c).get('FirmwarePackageVersion'),path_field(p,f'/Controllers/{i}/FirmwarePackageVersion'))
              for i,c in enumerate(arr(b.get('Controllers')))],
            *[(oem(c).get('FirmwarePackageVersion'),path_field(pp,'/Oem/*/FirmwarePackageVersion')) for pp,c in ports])
        cs.append(component('Сетевой адаптер',p,b,name=v.get('DeviceLocator') or b.get('Name'),
            model=b.get('Model') or chosen[1].get('Model'),part=pn[0],part_src=pn[1],serial=sn[0],serial_src=sn[1],
            fw=fw_value,fw_src=fw_source,
            extras={'Technology':v.get('NetworkTechnology'),'Slot':slot,'Ports':len(ports),
                    'PCIePath':chosen[0],'BoardPath':boardmatch[0],
                    'PortLinks':'; '.join(f'{q.rsplit("/",1)[-1]}:{x.get("LinkStatus")}' for q,x in ports)}))
    # Unmatched PCIe devices: do not drop FC/HBA/accelerator cards.
    for p,b in pci:
        if p in pci_used or is_absent(b):continue
        # Physical RAID adapter is already emitted from inline StorageControllers.
        # Match by nonempty hardware serial, not by a generic "RAID" label.
        card_sn=b.get('SerialNumber')
        if valid(card_sn) and any(c['Category']=='RAID/HBA' and c.get('SerialNumber')==card_sn for c in cs):
            continue
        cat='Сетевая PCIe карта' if 'net' in str(oem(b).get('FunctionType') or '').lower() else 'PCIe устройство'
        cs.append(component(cat,p,b,extras={'Type':oem(b).get('FunctionType'),'Slot':oem(b).get('SlotNumber')}))
    # Boards - preserve hardware identity except matched board for NIC.
    for p,b in boards:
        if p in board_used or is_absent(b):continue
        name=b.get('DeviceLocator') or b.get('Name')
        cs.append(component('Плата',p,b,name=name,model=b.get('BoardName') or b.get('Description'),
            fw=b.get('CPLDVersion'),fw_src=path_field(p,'/CPLDVersion'),extras={'BoardType':b.get('DeviceType'),'PCBVersion':b.get('PCBVersion')}))
    # Firmware items are distinct software snapshots; backup and available images
    # must not be treated as additional physically installed components.
    for p,b in firmwares:
        if not valid(b.get('Version')):continue
        result['FirmwareInventory'].append({'Name':b.get('Name') or b.get('Id') or p.rsplit('/',1)[-1],
           'Version':b.get('Version'),'State':status(b)['State'],'Health':status(b)['Health'],
           'SourcePath':p,'VersionSource':path_field(p,'/Version'),
           'Role':('Backup' if 'backup' in p.lower() else 'Available' if 'available' in p.lower() else 'Active' if 'active' in p.lower() else 'Current')})
    return result


def parse_file(file):
    with open(file,encoding='utf-8-sig') as f:raw=json.load(f)
    return parse_huawei(raw,str(file))
