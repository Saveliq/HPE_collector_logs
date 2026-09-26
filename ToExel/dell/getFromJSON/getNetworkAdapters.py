import re

from search import SYSTEM, CHASSIS, Resources, _dict, _list, _first, _installed, stripJSON


from getFromJSON.getDiagnostics import component_fields


def _identity(*values):
    for value in values:
        if isinstance(value, str) and value.strip().lower() not in {"", "unknown", "n/a", "none", "null"}:
            return value.strip()
    return None


def _adapter_details(resources, node):
    """Read OEM identity from this adapter's ports/functions, not other cards."""
    path = node.get("@odata.id", "").rstrip("/")
    children = resources.matching(re.escape(path) + r"/(?:NetworkDeviceFunctions|NetworkPorts|Ports)/[^/]+") if path else []
    for controller in _list(node.get("Controllers")):
        links = _dict(_dict(controller).get("Links"))
        for field in ("NetworkDeviceFunctions", "NetworkPorts", "Ports"):
            children.extend(resources.resolve(ref) for ref in _list(links.get(field)))
    details = []
    for child in [node] + children:
        for kind in ("DellFC", "DellNIC"):
            detail = resources.oem(child, kind)
            if detail:
                details.append(detail)
    # Some collections only contain separate OEM responses without a parent body.
    if path:
        details.extend(resources.matching(re.escape(path) +
                       r"/(?:NetworkDeviceFunctions|NetworkPorts|Ports)/[^/]+/Oem/Dell/(?:DellFC|DellNIC)/[^/]+"))
    return details


def get_network_adapters(json_data):
    resources = Resources(json_data)
    nodes = resources.matching(re.escape(CHASSIS) + r"/NetworkAdapters/[^/]+")
    nodes += resources.matching(re.escape(SYSTEM) + r"/NetworkAdapters/[^/]+")
    result = []
    seen = set()
    for node in _installed(resources, nodes, enrich_pcie=True):
        # Identical adapters exposed beneath Systems and Chassis have the same Id.
        key = node.get("Id") or node.get("@odata.id")
        if key and key in seen:
            continue
        if key:
            seen.add(key)
        details = _adapter_details(resources, node)
        # Use actual P/N first; a product/model name is the fallback for cards
        # such as QME2662 whose OEM PartNumber is explicitly null.
        node["Model"] = _identity(node.get("Model"),
                                  *(d.get("ProductName") for d in details),
                                  *(d.get("DeviceName") for d in details))
        node["PartNumber"] = _identity(node.get("PartNumber"),
                                       *(d.get("PartNumber") for d in details), node.get("Model"))
        node["SerialNumber"] = _identity(node.get("SerialNumber"),
                                         *(d.get("SerialNumber") for d in details))
        versions = []
        for controller in _list(node.get("Controllers")):
            version = component_fields(_dict(controller)).get("FirmwareVersion")
            if version and version not in versions:
                versions.append(version)
        node["FirmwareVersion"] = _first(node.get("FirmwareVersion"), "; ".join(versions))
        node["Name"] = _first(node.get("Model"), node.get("Id"), node.get("Name"))
        result.append(node)
    return stripJSON(result)


