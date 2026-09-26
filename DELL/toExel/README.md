# Dell → Excel

Запуск из корня проекта:

```powershell
python ToExel/dell/main.py
```

Выберите папку с JSON или ZIP выгрузками Dell. В выбранной папке появится
`Аудит_результаты.xlsx` с теми же листами **Аудит** и **Группировка_PN**,
колонками, группировкой и цветами состояний, что и в варианте HPE.
В колонке прошивки сервера выводятся BIOS и iDRAC.

Модули `getFromJSON` преобразуют эндпоинты Dell в поля экспортера.
Поддержаны обе схемы из локальной папки `examples`: адаптеры под `Systems`/`Chassis`,
встроенные и отдельные контроллеры Storage, оба расположения Drives.
P/N сервера берётся из `PartNumber` (при отсутствии — из `SKU`), политика
питания — из BIOS `SysProfile`, восстановление питания — из `AcPwrRcvry`.
Отсутствующие в выгрузке значения не дополняются вымышленными данными.

Для памяти колонка `DIMMStatus` берётся из одноимённого поля (включая OEM
`DellMemory`), а при его отсутствии — из `Status.Health`, затем `HealthRollup`
или `State`. Исходные колонки Health и State также сохраняются.
Для сетевых адаптеров P/N и серийный номер дополнительно читаются из OEM-данных
`DellFC`/`DellNIC` их портов. Если P/N отсутствует, используется модель,
`ProductName` или `DeviceName` (например, `QME2662`).
Для дисков P/N сначала берётся из `PartNumber` (включая OEM `DellPhysicalDisk`),
если это отдельный партномер. Значение, совпадающее с OEM `PPID` или имеющее
формат полного Dell PPID (с дефисами или без), пропускается.
Если отдельного партномера нет, используется `Model` (например, `HUC101860CSS200`).

Backplane выводится как «Дисковая корзина (backplane)», внешние полки — как
«Дисковая полка». Их P/N и S/N берутся из собственных полей ресурса:
ссылка на RAID-контроллер не переносит его идентификаторы в строку корзины.

Структура кода повторяет HPE:

```text
dell/
  main.py
  ParseJsonToExel.py
  getAllJSONs.py
  diagnostic_sheets.py
  search.py
  getFromJSON/
    getArrayControllers.py
    getChassis.py
    getDiagnostics.py
    getEmbeddedMedia.py
    getManager.py
    getMemory.py
    getNetworkAdapters.py
    getPCISlots.py
    getPower.py
    getProcessors.py
    getSystem.py
  examples/
    redfish_full.json
    redfish_full0.json
  tests/
    test_dell_export.py
```

Все модули, вспомогательные функции и тестовые данные находятся внутри `dell`.
Папку можно скопировать отдельно и запускать в ней `python main.py`.
Из внешних библиотек нужен `openpyxl`; для диалога выбора папки — `tkinter`.
Исходный экспорт HPE не изменён, формат и логика записи Excel сохранены.

Проверка из корня проекта:

```powershell
python -m unittest discover -s ToExel/dell/tests -v
```

Из самой папки `dell`: `python -m unittest discover -s tests -v`.
