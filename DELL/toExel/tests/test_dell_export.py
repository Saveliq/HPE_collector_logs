import contextlib
import copy
import io
import json
from collections import Counter
from pathlib import Path
import sys
import unittest

TO_EXEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TO_EXEL))
import ParseJsonToExel as export
from fleet_data import firmware_records, health_issues
from search import CHASSIS, MANAGER, SYSTEM
from sample_files import reference_files


class DellExportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.files = reference_files()
        if len(cls.files) != 10:
            raise AssertionError("All ten Dell example files are required")
        cls.raw = [json.loads(path.read_text(encoding="utf-8")) for path in cls.files]

    def test_inventory_counts_in_all_examples(self):
        fields = ("Processors", "Memory", "NetworkAdapters", "SmartStorage", "PhysicalDisks",
                  "PowerSupplies", "Fans", "StorageEnclosures", "StorageBatteries")
        counts = [(2,32,4,3,2,2,16,2,1), (2,32,4,3,2,2,16,1,1), (2,32,4,3,2,2,16,2,1),
                  (2,32,4,3,2,2,16,2,1), (2,16,3,3,12,2,16,1,0), (2,16,3,3,12,2,16,1,0),
                  (2,32,4,3,2,2,16,1,1), (2,16,3,4,10,2,16,1,0), (2,32,4,3,2,2,16,1,1),
                  (2,32,4,3,2,2,16,1,1)]
        for file, raw, expected in zip(self.files, self.raw, counts):
            with self.subTest(file=file.parent.name):
                data = export.parse_data(raw)
                self.assertEqual(tuple(len(data[field]) for field in fields), expected)

    def test_values_match_source_responses(self):
        for raw in self.raw:
            data = export.parse_data(raw)
            self.assertEqual(data["SKU"], raw[SYSTEM]["PartNumber"])
            self.assertEqual(data["SerialNumber"], raw[SYSTEM]["SerialNumber"])
            self.assertEqual(data["iDRACVersion"], raw[MANAGER]["FirmwareVersion"])
            self.assertEqual(data["BiosVersion"], raw[SYSTEM]["BiosVersion"])
            attrs = raw[SYSTEM + "/Bios"]["Attributes"]
            self.assertEqual(data["PowerRegulatorMode"], attrs["SysProfile"])
            self.assertEqual(data["PowerAutoOn"], attrs["AcPwrRcvry"])
            power_attrs = raw[MANAGER + "/Oem/Dell/DellAttributes/System.Embedded.1"]["Attributes"]
            for field, key in (("RedundancyPolicy", "PSRedPolicy"), ("HotSpare", "PSRapidOn"),
                               ("PrimaryPSU", "RapidOnPrimaryPSU")):
                self.assertEqual(data[field], power_attrs.get("ServerPwr.1." + key))
            self.assertEqual(data["PowerConsumedWatts"], raw[CHASSIS + "/Power"]["PowerControl"][0]["PowerConsumedWatts"])
            for memory in data["Memory"]:
                source = raw[memory["@odata.id"]]
                self.assertEqual(memory["SizeMB"], source["CapacityMiB"])
                self.assertEqual(memory["Frequency"], source["OperatingSpeedMhz"])
                self.assertEqual(memory["DIMMStatus"], source["Status"]["Health"])
            for disk in data["PhysicalDisks"]:
                source = raw[disk["@odata.id"]]
                self.assertEqual(disk["FirmwareVersion"], source["Revision"])
                self.assertAlmostEqual(disk["CapacityGB"], source["CapacityBytes"] / 1e9)
                self.assertEqual(disk["InterfaceSpeedMbps"], source["NegotiatedSpeedGbs"] * 1000)
            for enclosure in data["StorageEnclosures"]:
                source = raw[enclosure["@odata.id"]]
                self.assertEqual(enclosure.get("SerialNumber"), source.get("SerialNumber"))
                self.assertEqual(enclosure.get("PartNumber"), source.get("PartNumber"))

    def test_fragments_and_network_views_do_not_duplicate_inventory(self):
        raw = copy.deepcopy(self.raw[0])
        for path, node in list(raw.items()):
            if "#" not in path:
                raw[path + "#/duplicate"] = node
            if path.startswith(CHASSIS + "/NetworkAdapters/"):
                raw[path.replace(CHASSIS, SYSTEM)] = node
        before, after = export.parse_data(self.raw[0]), export.parse_data(raw)
        for field in ("Processors", "Memory", "NetworkAdapters", "SmartStorage", "PhysicalDisks", "PowerSupplies", "Fans"):
            self.assertEqual(before[field], after[field])
        self.assertEqual(firmware_records(before), firmware_records(after))

    def test_legacy_controllers_psu_and_fans(self):
        raw = {k: v for k, v in self.raw[0].items()
               if "/Controllers" not in k and "/PowerSubsystem/" not in k and "/ThermalSubsystem/" not in k}
        data = export.parse_data(raw)
        self.assertEqual(len(data["SmartStorage"]), 3)
        self.assertEqual(len(data["PowerSupplies"]), 2)
        self.assertEqual(len(data["Fans"]), 16)
        controller = next(c for c in data["SmartStorage"] if "PERC" in c["Model"])
        self.assertEqual(controller["PartNumber"], "0GT7YG")
        self.assertTrue(controller["SerialNumber"])

    def test_firmware_snapshots_and_ports_count_physical_devices(self):
        for raw in self.raw:
            data = export.parse_data(raw)
            records = firmware_records(data)
            for field in ("PhysicalDisks", "NetworkAdapters", "PowerSupplies", "SmartStorage"):
                current = [r for r in records if r["InstanceKey"][0] == field and r["FirmwareRole"] == "Текущая"]
                self.assertEqual(len(current), len(data[field]))
            self.assertTrue(any(r["FirmwareRole"] == "Previous" for r in records))
            cpu = [r for r in records if r["FirmwareRole"] == "MicrocodeInfo"]
            self.assertEqual(len(cpu), 2)
            self.assertEqual(len({r["InstanceKey"] for r in cpu}), 2)
            extra = [r for r in records if "/PCIeDevices/" in r.get("ComponentPath", "")
                     and r["InstanceKey"][0] not in {"SmartStorage", "NetworkAdapters", "PhysicalDisks"}]
            self.assertEqual(extra, [])
        records = firmware_records(export.parse_data(self.raw[0]))
        fc = [r for r in records if r["ComponentType"] == "FC HBA"]
        self.assertEqual(Counter(r["FirmwareRole"] for r in fc), {"Текущая": 1, "Previous": 1})
        bios = [r for r in records if r["InstanceKey"] == ("Software", "BIOS.Setup.1-1")]
        self.assertEqual(Counter(r["FirmwareRole"] for r in bios), {"Текущая": 1, "Previous": 1})

    def test_disk_ppid_and_real_part_numbers(self):
        from getFromJSON.getArrayControllers import get_array_controllers
        path = SYSTEM + "/Storage/Drives/Disk.1"
        raw = {path: {"@odata.id": path, "Name": "Disk", "Model": "HUC101860CSS200"}}
        for part in (None, "", "TH-06DWVP-HGT00-85M-4316-A00", "TW0919J9ITT0081302D4A00"):
            raw[path]["PartNumber"] = part
            self.assertEqual(get_array_controllers(raw)[1][0]["PartNumber"], "HUC101860CSS200")
        for part in ("06DWVP", "GENERIC-PART-123"):
            raw[path]["PartNumber"] = part
            self.assertEqual(get_array_controllers(raw)[1][0]["PartNumber"], part)

    def test_missing_failed_absent_zero_and_false_values(self):
        for raw in ({}, [], {SYSTEM: {"error": {"message": "unavailable"}}},
                    {"/redfish/v1/Systems/1": {"Model": "HPE"}}):
            self.assertIsNone(export.parse_data(raw))
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertIsNone(export.print_parser(TO_EXEL / "does-not-exist.json"))
        raw = {SYSTEM: {"Model": "Dell", "ProcessorSummary": {"Count": 2}},
               SYSTEM + "/Bios": {"Attributes": {"AcPwrRcvry": False, "TpmInfo": "No TPM present"}},
               SYSTEM + "/Processors/1": {"Name": "CPU", "Status": {"State": "Absent"}},
               SYSTEM + "/Memory/1": {"Name": "DIMM", "CapacityMiB": 0, "Status": {"State": "Disabled", "Health": "Critical"}},
               CHASSIS + "/Power": {"PowerControl": [{"PowerConsumedWatts": 0}]}}
        data = export.parse_data(raw)
        self.assertFalse(data["PowerAutoOn"])
        self.assertEqual(data["PowerConsumedWatts"], 0)
        self.assertIsNone(data["iDRACVersion"])
        self.assertNotIn("TrustedModules", data)
        self.assertEqual(data["Memory"][0]["DIMMStatus"], "Critical")
        self.assertEqual(data["Memory"][0]["SizeMB"], 0)
        self.assertEqual(health_issues(data)[0]["ComponentType"], "Память")
        from openpyxl import Workbook
        self.assertEqual(export.write_proc_info(Workbook().active, data, 1, 1)[0], 1)

    def test_project_imports_stay_inside_dell(self):
        import main
        self.assertEqual(main._parseJSONToExel, export._parseJSONToExel)
        names = ["main", "ParseJsonToExel", "search", "diagnostic_sheets", "fleet_data", "fleet_sheets", "getAllJSONs"]
        names += ["getFromJSON." + path.stem for path in (TO_EXEL / "getFromJSON").glob("*.py")]
        for name in names:
            self.assertTrue(Path(sys.modules[name].__file__).resolve().is_relative_to(TO_EXEL))


if __name__ == "__main__":
    unittest.main()
