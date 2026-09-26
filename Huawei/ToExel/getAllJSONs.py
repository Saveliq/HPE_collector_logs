import os
import zipfile
from pathlib import Path
from uuid import uuid4

def find_json_files(root_dir, temp_dir):
    """
    Извлекает json из архивов во временную папку.
    Возвращает список путей к распакованным JSON.
    """
    json_files = []
    temp_root = Path(temp_dir).resolve()
    extraction = None

    for root, dirs, files in os.walk(root_dir):
        # Do not rescan previously extracted JSON when tmp is below root_dir.
        dirs[:] = [name for name in dirs if (Path(root) / name).resolve() != temp_root]
        for file in files:
            filepath = os.path.join(root, file)

            # обычный JSON
            if file.lower().endswith(".json"):
                json_files.append(filepath)

            # ZIP архив
            elif file.lower().endswith(".zip"):
                try:
                    with zipfile.ZipFile(filepath, 'r') as zf:
                        for member in zf.infolist():
                            if member.filename.lower().endswith(".json") and not member.is_dir():
                                if extraction is None:
                                    extraction = temp_root / ("huawei_" + uuid4().hex)
                                    extraction.mkdir(parents=True)
                                # Different server archives commonly all contain
                                # redfish_full.json. Never overwrite earlier data.
                                extracted_path = extraction / (uuid4().hex + ".json")
                                extracted_path.write_bytes(zf.read(member))
                                json_files.append(str(extracted_path))
                except Exception as e:
                    print(f"[Ошибка ZIP] {filepath}: {e}")

    return json_files


