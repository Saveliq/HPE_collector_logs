"""Installed CPU inventory; Huawei/xFusion OEM P/N and S/N preserved."""
from ._common import components


def get_processors(json_data):
    return components(json_data, 'Процессор')
