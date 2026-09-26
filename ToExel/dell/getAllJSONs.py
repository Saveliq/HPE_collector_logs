import os
import zipfile
import tempfile

def find_json_files(root_dir, temp_dir):
    """
    Извлекает json из архивов во временную папку.
    Возвращает список путей к распакованным JSON.
    """
    json_files = []

    for root, dirs, files in os.walk(root_dir):
        for file in files:
            filepath = os.path.join(root, file)

            # обычный JSON
            if file.lower().endswith(".json"):
                json_files.append(filepath)

            # ZIP архив
            elif file.lower().endswith(".zip"):
                try:
                    with zipfile.ZipFile(filepath, 'r') as zf:
                        for name in zf.namelist():
                            if name.lower().endswith(".json"):
                                extracted_path = zf.extract(name, path=temp_dir)
                                json_files.append(extracted_path)
                except Exception as e:
                    print(f"[Ошибка ZIP] {filepath}: {e}")

    return json_files


