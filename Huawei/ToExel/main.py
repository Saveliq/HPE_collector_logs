"""Run: python main.py /path/to/logs [--output report.xlsx]
Or: python main.py /path/to/server_logs.zip --output report.xlsx
Without parameters a native folder dialog is offered when Tkinter is available.
"""
import argparse
from pathlib import Path
from tempfile import TemporaryDirectory
import zipfile

from huawei_parser import parse_file
from huawei_excel import export


def find_jsons(folder):
    return sorted(Path(folder).rglob('redfish_full.json'))


def run(path,output):
    path=Path(path)
    if path.suffix.lower()=='.zip':
        with TemporaryDirectory(prefix='huawei_redfish_') as temp:
            with zipfile.ZipFile(path) as zf:
                for item in zf.infolist():
                    target=Path(temp,item.filename).resolve()
                    if not target.is_relative_to(Path(temp).resolve()):raise ValueError('Unsafe zip path')
                    if item.filename.endswith('/redfish_full.json') or item.filename=='redfish_full.json':
                        target.parent.mkdir(parents=True,exist_ok=True)
                        target.write_bytes(zf.read(item))
            return _run_files(find_jsons(temp),output,root=Path(temp),archive=path.name)
    if path.is_file() and path.suffix.lower()=='.json':return _run_files([path],output,root=path.parent)
    return _run_files(find_jsons(path),output,root=path)


def _run_files(files,output,root=None,archive=None):
    if not files:raise ValueError('Не найдены redfish_full.json')
    items=[];seen=set()
    for p in files:
        try:s=parse_file(p)
        except (ValueError,OSError) as e:
            print('ERROR:',p,e);continue
        if not s:
            print('SKIP:',p,'not a Huawei/xFusion system');continue
        sn=s.get('SerialNumber')
        # Unknown S/N must never lead to false deduplication.
        key=('SN',sn) if sn else ('FILE',str(p))
        if key in seen:
            print('DUPLICATE:',p,'SN=',sn);continue
        seen.add(key)
        if root:
            relative=Path(p).relative_to(root).as_posix()
            s['SourceFile']=f'{archive}!{relative}' if archive else relative
        items.append(s)
    if not items:raise ValueError('Нет корректных JSON Huawei / xFusion')
    counts=export(items,output)
    print('READY:',output,'servers=',len(items),'components=',counts['Компоненты'],
          'firmware=',counts['Прошивки'],'issues=',counts['Проблемы'])
    return items,counts


def main():
    parser=argparse.ArgumentParser(description='Аудит Redfish Huawei/xFusion -> Excel')
    parser.add_argument('input',nargs='?',help='Папка, redfish_full.json или zip с логами')
    parser.add_argument('--output','-o',default='Аудит_Huawei.xlsx')
    args=parser.parse_args()
    if not args.input:
        from tkinter import Tk,filedialog
        root=Tk();root.withdraw();args.input=filedialog.askdirectory(title='Папка с redfish_full.json');root.destroy()
        if not args.input:return
    run(args.input,args.output)


if __name__=='__main__':main()
