from tkinter import Tk, filedialog
from ParseJsonToExel import _parseJSONToExel
from getAllJSONs import find_json_files


if __name__ == '__main__':
    # Отключаем основное окно Tkinter
    root = Tk()
    root.withdraw()

    # Диалог выбора директории
    folder_selected = filedialog.askdirectory(title="Выберите папку для поиска JSON-файлов")

    if folder_selected:
        # Вторая переменная ("tmp") может указывать на временную директорию или имя папки для извлечённых файлов
        json_files = find_json_files(folder_selected, "tmp")
        _parseJSONToExel(json_files, folder_selected)
    else:
        print("Папка не выбрана. Работа программы завершена.")
