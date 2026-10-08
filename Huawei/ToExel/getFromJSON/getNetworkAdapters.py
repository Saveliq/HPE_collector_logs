"""Huawei NetworkAdapters normalized from hardware-owning Redfish resources.

PCIe/Board alternatives are used only where unique by physical location/slot.
"""
from ._common import components


def get_network_adapters(json_data):
    return components(json_data,'Сетевой адаптер')
