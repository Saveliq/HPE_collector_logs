import re

from search import search_one, stripJSON, is_absent
from getFromJSON.getDiagnostics import component_fields


def get_embedded_media(json_data):
    result = {}
    data = json_data.get('/redfish/v1/Managers/1/EmbeddedMedia', {})
    result["SDCard"] = search_one(data, r"State", path_pattern="SDCard")
    result["USBDevices"] = [dict(device, **component_fields(device))
                            for path, device in json_data.items()
                            if re.fullmatch(r".*/USBDevices/[^/#]+", path)
                            and isinstance(device, dict) and device.get("DeviceName")
                            and not is_absent(device)]
    return stripJSON(result)

