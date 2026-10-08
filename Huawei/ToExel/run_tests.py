"""Run exhaustive checks of an already exported Excel against source Redfish dumps.
Usage: python run_tests.py server_logs_Huawei_AB.zip Huawei_Аудит_результаты.xlsx
"""
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import zipfile


def main():
    if len(sys.argv)!=3:
        raise SystemExit('Usage: python run_tests.py <logs-directory-or-zip> <excel-file>')
    file=Path(sys.argv[1]).resolve();report=Path(sys.argv[2]).resolve()
    if not report.is_file():raise SystemExit('Excel file not found')
    with TemporaryDirectory(prefix='huawei_test_') as td:
        if file.is_file() and file.suffix.lower()=='.zip':
            with zipfile.ZipFile(file) as z:
                for entry in z.infolist():
                    if entry.filename.endswith('/redfish_full.json') or entry.filename=='redfish_full.json':
                        dest=Path(td,entry.filename).resolve()
                        if not dest.is_relative_to(Path(td).resolve()):raise ValueError('Unsafe zip entry')
                        dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(z.read(entry))
            logs=Path(td)
        else:logs=file
        env=dict(os.environ,HUAWEI_LOGS=str(logs),HUAWEI_XLSX=str(report))
        return subprocess.call([sys.executable,'-m','unittest','discover','-s','tests','-v'],cwd=Path(__file__).parent,env=env)


if __name__=='__main__':sys.exit(main())
