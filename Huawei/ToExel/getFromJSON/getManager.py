from search import Resources, first_value


def get_manager(json_data):
    resources = Resources(json_data)
    manager = resources.resolve(resources.manager_path)
    active = resources.resolve("/redfish/v1/UpdateService/FirmwareInventory/ActiveBMC")
    return {"iBMCVersion": first_value(manager.get("FirmwareVersion"), active.get("Version"))}
