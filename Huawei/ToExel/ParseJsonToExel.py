"""Compatibility entry point for existing integrations."""
from main import run
from huawei_parser import parse_huawei as parse_data

def _parseJSONToExel(json_files,folder_selected):
    from pathlib import Path
    from main import _run_files
    return _run_files(list(map(Path,json_files)),Path(folder_selected)/'Аудит_результаты.xlsx')
