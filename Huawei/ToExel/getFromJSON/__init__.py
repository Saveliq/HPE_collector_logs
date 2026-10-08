"""Huawei/xFusion Redfish field extraction modules.

The public get_* names match the original toExel project's getFromJSON package.
For the new full inventory exporter use main.py / huawei_parser.py.
"""
from .getSystem import get_system
from .getChassis import get_chassis
from .getManager import get_manager
from .getProcessors import get_processors
from .getMemory import get_memory
from .getArrayControllers import get_array_controllers, get_storage_enclosures
from .getPower import get_power, get_power_consumption
from .getNetworkAdapters import get_network_adapters
from .getPCISlots import get_PCI_slots
from .getEmbeddedMedia import get_embedded_media
from .getDiagnostics import get_diagnostics
