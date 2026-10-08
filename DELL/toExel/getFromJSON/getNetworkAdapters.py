import re

from search import SYSTEM, CHASSIS, Resources, _dict, _list, _first, _installed, stripJSON
from getFromJSON.getDiagnostics import component_fields


INVALID_IDENTITY = {"", "unknown", "n/a", "na", "none", "null", "not available", "notavailable"}
MAC_SUFFIX = re.compile(r"\s+-\s+(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$")


def _identity(*values):
    for value in values:
        if isinstance(value, str) and value.strip().lower() not in INVALID_IDENTITY:
            return value.strip()
    return None


def _product_model(value):
    value = _identity(value)
    if not value:
        return None
    # Dell port ProductName frequently ends in " - <MAC>".  That suffix is a
    # port instance identifier, not the adapter model and must never become P/N.
    return MAC_SUFFIX.sub("", value).strip()


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
        # Embedded LOM adapters omit PCIe links. Dell's port inventory exposes
        # the PCI bus; use it only when it identifies one device in this chassis.
        buses = {str(d["BusNumber"]) for d in details if d.get("BusNumber") is not None}
        if len(buses) == 1:
            bus = next(iter(buses))
            devices = resources.matching(re.escape(CHASSIS + "/PCIeDevices/" + bus) + r"-[^/]+")
            if len(devices) == 1:
                node["SourceAliases"].append(devices[0]["@odata.id"])

        product_names = [_product_model(d.get("ProductName")) for d in details]
        device_names = [_product_model(d.get("DeviceName")) for d in details]
        node["Model"] = _identity(_product_model(node.get("Model")), *product_names, *device_names)

        # P/N must be a real PartNumber.  Do not substitute ProductName/Model:
        # on embedded BCM5720 adapters that value contains a port MAC address and
        # was previously written to Excel as if it were a part number.
        node["PartNumber"] = _identity(node.get("PartNumber"), *(d.get("PartNumber") for d in details))
        node["SerialNumber"] = _identity(node.get("SerialNumber"), *(d.get("SerialNumber") for d in details))

        versions = []
        for controller in _list(node.get("Controllers")):
            version = component_fields(_dict(controller)).get("FirmwareVersion")
            if version and version not in versions:
                versions.append(version)
        node["FirmwareVersion"] = _first(node.get("FirmwareVersion"), "; ".join(versions))
        node["Name"] = _first(node.get("Model"), node.get("Id"), node.get("Name"))
        result.append(node)
    return stripJSON(result)
