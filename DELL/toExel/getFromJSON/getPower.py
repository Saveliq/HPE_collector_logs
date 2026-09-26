from search import Resources, stripJSON
from getFromJSON.getChassis import _chassis_components


def get_power(json_data):
    return stripJSON(_chassis_components(
        Resources(json_data), "/Power", "PowerSupplies", "/PowerSubsystem/PowerSupplies"))
