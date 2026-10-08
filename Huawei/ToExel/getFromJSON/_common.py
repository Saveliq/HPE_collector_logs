"""Source-preserving adapters between the normalized Huawei parser and the old API.

Never substitute Model/Name for missing PartNumber or manufacture component S/Ns.
"""
from huawei_parser import parse_huawei, obj, arr, oem, valid, is_absent, collection_base, descendants


def parsed(raw):
    result = parse_huawei(raw)
    if result is None:
        raise ValueError('Expected a redfish_full.json mapping for Huawei/xFusion')
    return result


def body_at(raw, source):
    """Resolve an exact Redfish URL#JSON-pointer (and OEM wildcard)."""
    if not source:
        return {}
    url, *fragments = source.split('#')
    val = raw.get(url)
    for fragment in fragments:
        for part in fragment.lstrip('/').split('/'):
            if not part:
                continue
            part = part.replace('~1', '/').replace('~0', '~')
            if part == '*':
                val = oem({'Oem':val}) if isinstance(val,dict) else {}
            elif isinstance(val, list):
                try: val = val[int(part)]
                except (ValueError, IndexError): return {}
            elif isinstance(val, dict):
                val = val.get(part)
            else:
                return {}
    return obj(val)
    for part in fragment.lstrip('/').split('/'):
        if not part:
            continue
        part = part.replace('~1', '/').replace('~0', '~')
        if part == '*':
            val = oem({'Oem':val}) if isinstance(val,dict) else {}
        elif isinstance(val, list):
            try: val = val[int(part)]
            except (ValueError, IndexError): return {}
        elif isinstance(val, dict):
            val = val.get(part)
        else:
            return {}
    return obj(val)


def normalize_component(raw, item):
    """Preserve native keys and expose normalized component fields and provenances."""
    out = dict(body_at(raw, item['SourcePath']))
    out.update({
        'Name': item.get('Name'), 'Model': item.get('Model'),
        'PartNumber': item.get('PartNumber'), 'SerialNumber': item.get('SerialNumber'),
        'FirmwareVersion': item.get('FirmwareVersion'),
        'SourcePath': item['SourcePath'],
        'PartNumberSource': item.get('PartNumberSource'),
        'SerialNumberSource': item.get('SerialNumberSource'),
        'FirmwareSource': item.get('FirmwareSource'),
        'State': item.get('State'), 'Health': item.get('Health'),
        'HealthRollup': item.get('HealthRollup'),
    })
    out.update(item.get('Info') or {})
    return out


def components(raw, *categories):
    data = parsed(raw)
    return [normalize_component(raw, item) for item in data['Components'] if item['Category'] in categories]
