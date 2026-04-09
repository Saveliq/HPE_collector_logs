import os

import json
from pathlib import Path
from openpyxl import Workbook


# === CONFIGURATION ===
OUTPUT_PATH = Path("Аудит_результаты.xlsx")
SERVER_NUMBER = 1
PN_SUMMARY = {}  # server_index -> {PN -> {count, names, description}}
CURRENT_SERVER_INDEX = None
INVALID_IDENTIFIERS = {"", "none", "null", "nan", "n/a", "na", "unknown", "notpresent", "absent"}

# Порядок и подписи полей, которые нужно извлекать из JSON
FIELDS = [
    ("SKU", "SKU"),
    ("SerialNumber", "Серийный номер"),
    ("Model", "Модель"),
    ("FirmwareVersion", "Версия прошивки"),
    ("BiosVersion", "BIOS версия"),
    ("PowerState", "Состояние питания"),
    ("ServerHealth", "Здоровье сервера"),
    ("MemorySummaryHealth", "Состояние памяти"),
    # Добавьте другие поля по мере необходимости
]


def _to_text(value, default=""):
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _is_invalid_identifier(value):
    normalized = _to_text(value, "").strip().lower()
    return normalized in INVALID_IDENTIFIERS


def _normalize_part_number(part_number, spare_part_number="", component_name=""):
    primary = _to_text(part_number, "")
    spare = _to_text(spare_part_number, "")

    if _is_invalid_identifier(primary):
        primary = ""
    if _is_invalid_identifier(spare):
        spare = ""

    normalized = primary or spare
    if normalized:
        return normalized

    component_key = _to_text(component_name, "UNKNOWN_COMPONENT").replace(" ", "_")
    return f"UNKNOWN_PN::{component_key}"


def _ensure_list(value):
    return value if isinstance(value, list) else []


def _server_unique_key(server_pn, server_sn, server_model):
    normalized_sn = _to_text(server_sn, "")
    if not _is_invalid_identifier(normalized_sn):
        return ("SN", normalized_sn.upper())

    normalized_pn = _to_text(server_pn, "")
    normalized_model = _to_text(server_model, "")
    return ("FALLBACK", normalized_pn.upper(), normalized_model.upper())


def _unique_by_sn(components, prefix):
    unique_components = []
    seen = set()
    missing_sn_index = 1

    for component in _ensure_list(components):
        if not isinstance(component, dict):
            continue

        serial_number = _to_text(component.get("SerialNumber"), "")
        if _is_invalid_identifier(serial_number):
            serial_number = ""

        if serial_number:
            dedupe_key = ("SN", serial_number.upper())
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)

        if not serial_number:
            serial_number = f"{prefix}_NO_SN_{missing_sn_index}"
            missing_sn_index += 1

        normalized_component = dict(component)
        normalized_component["SerialNumber"] = serial_number
        unique_components.append(normalized_component)

    return unique_components


def _register_pn_summary(part_number, component_name, description):
    if CURRENT_SERVER_INDEX is None:
        return
    
    if CURRENT_SERVER_INDEX not in PN_SUMMARY:
        PN_SUMMARY[CURRENT_SERVER_INDEX] = {}
    
    server_data = PN_SUMMARY[CURRENT_SERVER_INDEX]
    summary = server_data.setdefault(
        part_number,
        {
            "count": 0,
            "names": set(),
            "example_description": "",
        },
    )
    summary["count"] += 1
    if component_name:
        summary["names"].add(component_name)

    if not summary["example_description"]:
        summary["example_description"] = _to_text(description, _to_text(component_name, ""))


def _write_component_row(
    ws,
    row,
    serial_number,
    part_number,
    component_name,
    spare_part_number="",
    description="",
    quantity=1,
    comment="",
):
    normalized_part_number = _normalize_part_number(part_number, spare_part_number, component_name)

    ws.cell(row=row, column=2, value=_to_text(serial_number))
    ws.cell(row=row, column=3, value=normalized_part_number)
    ws.cell(row=row, column=4, value=_to_text(component_name))
    ws.cell(row=row, column=5, value=_to_text(spare_part_number))
    ws.cell(row=row, column=6, value=_to_text(description))
    ws.cell(row=row, column=7, value=quantity)
    ws.cell(row=row, column=8, value=_to_text(comment))
    _register_pn_summary(normalized_part_number, component_name, description)
    return row + 1


def write_pn_summary_sheet(ws, server_rows):
    row = 1
    
    for server_index, server_row in enumerate(server_rows):
        # Заголовки таблицы компонентов
        ws.cell(row=row, column=1, value="P/N")
        ws.cell(row=row, column=2, value="Компонент")
        ws.cell(row=row, column=3, value="Количество")
        ws.cell(row=row, column=4, value="Описание (пример)")
        
        row += 1
        
        # Данные для этого сервера
        server_pn_data = PN_SUMMARY.get(server_index, {})
        sorted_items = sorted(server_pn_data.items(), key=lambda item: (-item[1]["count"], item[0]))
        
        for part_number, summary in sorted_items:
            component_names = ", ".join(sorted(summary["names"])) if summary["names"] else "UNKNOWN_COMPONENT"
            ws.cell(row=row, column=1, value=part_number)
            ws.cell(row=row, column=2, value=component_names)
            ws.cell(row=row, column=3, value=summary["count"])
            ws.cell(row=row, column=4, value=summary["example_description"])
            row += 1
        
        # Пустая строка между серверами
        row += 1
    
    return row


def write_proc_info(ws, server_data, start_row, start_col):
    processors = _unique_by_sn(server_data.get("Processors"), "CPU")

    if processors:
        for processor in processors:
            description = processor.get("Model") or processor.get("Name") or "Процессор"
            comment = {
                "Manufacturer": processor.get("Manufacturer"),
                "State": processor.get("State"),
                "Health": processor.get("Health"),
            }
            start_row = _write_component_row(
                ws,
                start_row,
                serial_number=processor.get("SerialNumber"),
                part_number=processor.get("PartNumber"),
                component_name="Процессор",
                description=description,
                quantity=1,
                comment=str(comment),
            )
        return (start_row, 5)

    processor_model = _to_text(server_data.get("ProcessorModel"), "Процессор")
    try:
        processor_count = int(server_data.get("ProcessorCount") or 0)
    except (TypeError, ValueError):
        processor_count = 0

    if processor_count <= 0 and processor_model:
        processor_count = 1

    for index in range(1, processor_count + 1):
        start_row = _write_component_row(
            ws,
            start_row,
            serial_number=f"CPU_NO_SN_{index}",
            part_number="",
            component_name="Процессор",
            description=processor_model,
            quantity=1,
            comment="Серийный номер не найден в источнике",
        )

    return (start_row, 5)

def write_NIC_info(ws, server_data, start_row, start_col):
    network_adapters = _unique_by_sn(server_data.get("NetworkAdapters"), "NIC")

    for nic in network_adapters:
        start_row = _write_component_row(
            ws,
            start_row,
            serial_number=nic.get("SerialNumber"),
            part_number=nic.get("PartNumber"),
            component_name="Сетевой адаптер",
            description=nic.get("Name"),
            quantity=1,
            comment=str({"Model": nic.get("Model"), "FirmwareVersion": nic.get("FirmwareVersion")}),
        )

    return (start_row, 5)

def write_RAID_info(ws, server_data, start_row, start_col):
    raid_controllers = []
    for raid in _ensure_list(server_data.get("SmartStorage")):
        if isinstance(raid, dict) and raid.get("LocationFormat") == "PCISlot":
            raid_controllers.append(raid)

    for raid in _unique_by_sn(raid_controllers, "RAID"):
        description = {
            "Model": raid.get("Model"),
            "CacheMemorySizeMiB": raid.get("CacheMemorySizeMiB"),
            "CurrentOperatingMode": raid.get("CurrentOperatingMode"),
        }
        comment = {"State": raid.get("State"), "Health": raid.get("Health")}
        start_row = _write_component_row(
            ws,
            start_row,
            serial_number=raid.get("SerialNumber"),
            part_number=raid.get("PartNumber"),
            component_name="RAID контроллер",
            description=str(description),
            quantity=1,
            comment=str(comment),
        )

        if raid.get("BackupPowerSourceStatus") == "Present":
            battery_spare = _to_text(server_data.get("StorageBattery"), "UNKNOWN")
            start_row = _write_component_row(
                ws,
                start_row,
                serial_number=f"{raid.get('SerialNumber')}-BAT",
                part_number=battery_spare,
                component_name="RAID батарея",
                spare_part_number=battery_spare,
                description="Батарея резервного питания RAID",
                quantity=1,
                comment="",
            )

    return (start_row, 5)


def write_MEM_info(ws, server_data, start_row, start_col):
    memory_modules = []
    for dimm in _ensure_list(server_data.get("Memory")):
        if isinstance(dimm, dict) and dimm.get("DIMMStatus") != "NotPresent":
            memory_modules.append(dimm)

    for dimm in _unique_by_sn(memory_modules, "DIMM"):
        description = {
            "SizeMB": dimm.get("SizeMB"),
            "Frequency": dimm.get("Frequency"),
            "Rank": dimm.get("Rank"),
            "Technology": dimm.get("Technology"),
        }
        part_number = dimm.get("PartNumber") or dimm.get("Model")
        start_row = _write_component_row(
            ws,
            start_row,
            serial_number=dimm.get("SerialNumber"),
            part_number=part_number,
            component_name="Память",
            description=str(description),
            quantity=1,
            comment=dimm.get("Manufacturer"),
        )

    return (start_row, 5)

def write_PSU_info(ws, server_data, start_row, start_col):
    power_supplies = _unique_by_sn(server_data.get("PowerSupplies"), "PSU")

    for psu in power_supplies:
        part_number = psu.get("PartNumber") or psu.get("SparePartNumber")
        description = {
            "Name": psu.get("Name"),
            "Model": psu.get("Model"),
            "PowerCapacityWatts": psu.get("PowerCapacityWatts"),
        }
        comment = {"State": psu.get("State"), "Health": psu.get("Health")}
        start_row = _write_component_row(
            ws,
            start_row,
            serial_number=psu.get("SerialNumber"),
            part_number=part_number,
            component_name="Блок питания",
            spare_part_number=psu.get("SparePartNumber"),
            description=str(description),
            quantity=1,
            comment=str(comment),
        )

    return (start_row, 5)

def write_DISK_info(ws, server_data, start_row, start_col):
    physical_disks = _unique_by_sn(server_data.get("PhysicalDisks"), "DISK")

    for disk in physical_disks:
        part_number = disk.get("PartNumber") or disk.get("Model")
        description = {
            "Model": disk.get("Model"),
            "CapacityGB": disk.get("CapacityGB"),
            "MediaType": disk.get("MediaType"),
        }
        comment = {
            "InterfaceType": disk.get("InterfaceType"),
            "InterfaceSpeedMbps": disk.get("InterfaceSpeedMbps"),
            "FirmwareVersion": disk.get("FirmwareVersion"),
        }
        start_row = _write_component_row(
            ws,
            start_row,
            serial_number=disk.get("SerialNumber"),
            part_number=part_number,
            component_name="Диск",
            description=str(description),
            quantity=1,
            comment=str(comment),
        )

    return (start_row, 5)

def write_other_info(ws, server_data, start_row, start_col):
    if server_data.get("SDCard", "") != "Absent":
        start_row = _write_component_row(
            ws,
            start_row,
            serial_number="SDCARD_NO_SN_1",
            part_number="",
            component_name="SDCard",
            description="Найден SDCard модуль",
            quantity=1,
        )

    if server_data.get("TrustedModules", "") not in ["NotPresent", "Absent"]:
        start_row = _write_component_row(
            ws,
            start_row,
            serial_number="TPM_NO_SN_1",
            part_number="",
            component_name="TrustedModule",
            description="Найден модуль доверенной платформы",
            quantity=1,
        )

    return (start_row, 5)

def extract_json_from_text(text: str) -> dict:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find('{')
        end = text.rfind('}') + 1
        try:
            return json.loads(text[start:end])
        except Exception:
            return {}

def write_desc_info(ws, start_row, current_col):
    Values = ["№", "S/N", "P/N", "Наименование", "Spare P/N", "Description", "Quantity", "Комментарий"]
    for column in range(len(Values)):
        ws.cell(row=start_row, column=current_col + column, value=Values[column])
    return (start_row + 1, 1)


def write_server_info(ws, server_data, start_row, current_col):
    ws.cell(row=start_row, column=1, value=SERVER_NUMBER)
    ws.cell(row=start_row, column=2, value=server_data.get("SerialNumber"))
    ws.cell(row=start_row, column=3, value=server_data.get("SKU"))
    ws.cell(row=start_row, column=4, value=server_data.get("Model"))
    start_row += 1
    return (start_row, 4+1)
from getFromJSON.getArrayControllers import get_array_controllers
from getFromJSON.getChassis import get_chassis
from getFromJSON.getEmbeddedMedia import get_embedded_media
from getFromJSON.getManager import get_manager
from getFromJSON.getMemory import get_memory
from getFromJSON.getNetworkAdapters import get_network_adapters
from getFromJSON.getPCISlots import get_PCI_slots
from getFromJSON.getProcessors import get_processors
from getFromJSON.getPower import get_power
from getFromJSON.getSystem import get_system


def print_parser(file_name):
    print("-" * 50)
    with open(file_name, 'r', encoding='utf-8') as f:

        try:
            raw_data = json.load(f)
            if not raw_data.get('/redfish/v1/Chassis/1', None):
                return None
        except Exception as e:
            return None
        data = None
        data = get_chassis(raw_data)
        data.update(get_manager(raw_data))
        data.update(get_system(raw_data))
        data["PowerSupplies"] = get_power(raw_data)
        data["Processors"] = get_processors(raw_data)
        data.update(get_embedded_media(raw_data))
        data["NetworkAdapters"] = get_network_adapters(raw_data)
        data.update(get_PCI_slots(raw_data))
        data["SmartStorage"], data["PhysicalDisks"] = get_array_controllers(raw_data)
        data["Memory"] = get_memory(raw_data)
        print(json.dumps(data, indent=4))
        return data
    print("-"*50)

def _parseJSONToExel(json_files, folder_selected):
    global SERVER_NUMBER, CURRENT_SERVER_INDEX
    PN_SUMMARY.clear()
    SERVER_NUMBER = 1
    CURRENT_SERVER_INDEX = None
    server_rows = []
    processed_servers = set()
    wb_out = Workbook()
    ws_out = wb_out.active
    ws_out.title = "Аудит"
    current_row = 1
    current_col = 1

    current_row, current_col = write_desc_info(ws_out, current_row, 1)
    for json_file in json_files:
        print(f"Обрабатывается файл: {json_file}")
        data = print_parser(str(json_file))
        if data is None:
            continue

        server_pn = _to_text(data.get("SKU"), "UNKNOWN_SERVER_PN")
        server_sn = _to_text(data.get("SerialNumber"), "UNKNOWN_SERVER_SN")
        server_model = _to_text(data.get("Model"), "UNKNOWN_SERVER_MODEL")
        server_key = _server_unique_key(server_pn, server_sn, server_model)

        if server_key in processed_servers:
            print(f"Пропуск дублирующегося сервера: SN={server_sn}, PN={server_pn}, Model={server_model}")
            continue

        processed_servers.add(server_key)
        server_rows.append((server_pn, server_sn, server_model))
        CURRENT_SERVER_INDEX = len(server_rows) - 1

        # запись информации о сервере
        current_row, current_col = write_server_info(ws_out, data, current_row, current_col)
        current_row, current_col = write_proc_info(ws_out, data, current_row, current_col)
        current_row, current_col = write_NIC_info(ws_out, data, current_row, current_col)
        current_row, current_col = write_RAID_info(ws_out, data, current_row, current_col)
        current_row, current_col = write_MEM_info(ws_out, data, current_row, current_col)
        current_row, current_col = write_DISK_info(ws_out, data, current_row, current_col)
        current_row, current_col = write_PSU_info(ws_out, data, current_row, current_col)
        current_row, current_col = write_other_info(ws_out, data, current_row, current_col)

        # пустая строка между серверами
        current_row += 2
        SERVER_NUMBER += 1

    if PN_SUMMARY:
        ws_pn = wb_out.create_sheet(title="Группировка_PN")
        write_pn_summary_sheet(ws_pn, server_rows)

    wb_out.save(os.path.join(folder_selected, OUTPUT_PATH))
    # wb_out.save(folder_selecteded+OUTPUT_PATH)
    print(f"OK. Audit saved: {OUTPUT_PATH}")


