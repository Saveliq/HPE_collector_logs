from search import Resources, as_list


def get_power(json_data):
    resources = Resources(json_data)
    nodes = resources.children(resources.chassis_path, "PowerSubsystem/PowerSupplies")
    if not nodes:
        nodes = as_list(resources.resolve(resources.chassis_path + "/Power").get("PowerSupplies"))
    return resources.installed(nodes)
