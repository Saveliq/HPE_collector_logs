from search import Resources


def get_embedded_media(json_data):
    resources = Resources(json_data)
    # VirtualMedia/USBStick is a remote virtual drive, not a physical USB device.
    nodes = resources.children(resources.system_path, "USBDevices")
    nodes += resources.children(resources.chassis_path, "USBDevices")
    return {"USBDevices": resources.installed(nodes)}
