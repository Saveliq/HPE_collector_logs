"""Huawei Chassis/Power: inline PowerSupplies, PowerControl and Redundancy."""
from ._common import components, parsed


def get_power(json_data):
    return components(json_data,'Блок питания')


def get_power_consumption(json_data):
    return parsed(json_data)['PowerConsumedWatts']


def get_psu_modes(json_data):
    """Modes as reported separately by each installed PSU, never inferred."""
    return parsed(json_data)['PSUModes']


def get_power_redundancy(json_data):
    """Redfish Redundancy groups with their explicit Health/Enabled fields."""
    return parsed(json_data)['RedundancyGroups']
