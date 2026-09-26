# Huawei → Excel

Запуск из корня проекта:

```powershell
python Huawei/ToExel/main.py
```

Выберите папку с JSON/ZIP выгрузками Huawei iBMC. Результат —
`Аудит_результаты.xlsx` в выбранной папке. Формат скопирован из HPE:
листы **Аудит** и **Группировка_PN**, 15 колонок, группировка по P/N и цвета
состояний. В строке сервера указаны BIOS и iBMC.

Структура сохранена: `main.py`, `ParseJsonToExel.py`, `getAllJSONs.py`,
`diagnostic_sheets.py`, `search.py` и те же 11 модулей `getFromJSON`.
Все проектные зависимости и пример находятся внутри `Huawei/ToExel`.
Папку можно переносить отдельно. Требуются Python, `openpyxl` и `tkinter`.

## Соответствие полей и компонентов

- Сервер: собственные `PartNumber`, `SerialNumber`, `Model` из Systems/Chassis.
  Политика питания — текущий BIOS `CustomPowerPolicy`, восстановление питания —
  `Oem.Huawei.PowerOnStrategy`. Настройки BIOS/Settings не подменяют действующие.
- Процессоры: собственные OEM Huawei `PartNumber` и `SerialNumber`.
- Память: `CapacityMiB`, `OperatingSpeedMhz`, `RankCount`, `MemoryDeviceType`,
  P/N из `PartNumber` или OEM `OriginalPartNumber`.
  `DIMMStatus` заполняется из собственного статуса DIMM; при его отсутствии
  используются `Health`, `HealthRollup` или `State`.
- RAID: `Storages/*/StorageControllers`, P/N и модель карты — по точной ссылке
  `Oem.Huawei.AssociatedCard` на Boards. Контроллер и его плата дают одну строку.
- Диски: ресурсы Chassis/Drives и ссылки Storage объединяются по ресурсу/S/N.
  P/N берётся из собственного поля, затем из модели. Объём — CapacityBytes / 10⁹,
  скорость интерфейса — NegotiatedSpeedGbs × 1000. Volumes не считаются дисками.
- Сеть: NetworkAdapter, NetworkInterface и явно связанное PCIe-устройство
  объединяются. Дополнительные PCIe-карты также включаются: Intel PRO/1000
  в примере отсутствует в NetworkAdapters и распознаётся по Description.
  У QLogic используется модель `QLE2692-HUA-SP`, а не название чипа `Qlipper`.
- LOM с тем же FRU S/N, что и MainBoard, относится к системной плате;
  модель и состав её встроенных портов записываются в комментарий к плате.
  Отдельная физическая карта LOM с другим S/N остаётся отдельной строкой.
- Системная плата, PCIe райзер и дисковый backplane имеют собственные строки.
  Backplane не получает идентификаторы связанного RAID-контроллера.
- Блоки питания берутся из Power/PowerSupplies, со своей прошивкой и мощностью.
- В примере нет ответа Thermal. Четыре вентилятора определяются по отдельным
  датчикам `FANn Speed` с показаниями RPM; это отмечено в комментариях.
  Их P/N и S/N отсутствуют. Шестнадцатеричные маски датчиков не интерпретируются.

Отсутствующие поля не выдумываются. Как в HPE, вместо неизвестных P/N и S/N
экспортёр использует явные маркеры `UNKNOWN_PN::…` и `…_NO_SN_…`.
Виртуальные USB/CD, максимальное число слотов и логические тома не добавляют
физических компонентов. Пустые слоты исключаются, неисправные компоненты остаются.

В `examples/redfish_full.json` ожидается 28 компонентов: 2 CPU, 8 DIMM,
1 RAID, 6 дисков, 2 отдельных сетевых адаптера, 2 PSU, 4 вентилятора,
1 системная плата со встроенным LOM, 1 PCIe райзер и 1 backplane.
Отдельного P/N и S/N Intel PRO/1000 в этой выгрузке нет.

## Проверка

Из корня проекта:

```powershell
python -m unittest discover -s Huawei/ToExel/tests -v
```

Или из папки `Huawei/ToExel`: `python -m unittest discover -s tests -v`.
Проверяются значения по источнику, отсутствие повторного учёта плат, дубли
ссылок и JSON серверов, пустые/ошибочные ответы, сохранение числового нуля,
статусы, запись/чтение XLSX и одноимённые JSON в разных ZIP.
