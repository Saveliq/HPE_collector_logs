# Redfish -> Excel fixes

Изменения сделаны по результатам сверки итоговой таблицы с 111 реальными `redfish_full.json` из `server_logs_DELL_AB.7z`.

## Исправлено

- На листе «Аудит» второй столбец — `Dell Service Tag`; столбец S/N удалён. Service Tag выводится только в строках серверов, без повторной колонки в конце таблицы.
- `TrustedModules` (TPM) больше не схлопывается в одну пустую строку: сохраняются `InterfaceType`, `FirmwareVersion`, `State`, `Health`, `HealthRollup`.
- `CapacityMiB` памяти больше не подписывается как `SizeMB`; используется `SizeMiB`.
- Для NIC `ProductName`/`Model` больше не подставляется в `PartNumber`; MAC-суффикс удаляется из fallback-модели.
- Для дисков `Not Available`/`NotAvailable` считается отсутствующим P/N и используется fallback на `Model`.
- Storage-контроллеры больше не называются все подряд RAID: выделяются RAID, HBA, BOSS/boot и SATA/AHCI.
- Потребление сначала читается из `/Chassis/System.Embedded.1/EnvironmentMetrics -> PowerWatts.Reading`, с fallback на legacy `/Power -> PowerControl[0].PowerConsumedWatts`.
- Значение `Not Available` добавлено в список отсутствующих идентификаторов/отображаемых пустых значений.

## Проверка на предоставленных данных

- 111/111 Service Tag совпали с Dell OEM `ServiceTag`.
- TPM: 87 строк, из них 86 `Disabled` и 1 `Enabled`; у включенного TPM сохранена прошивка `7.2.3.1`.
- NIC P/N, заканчивающихся MAC-адресом: 0.
- Дисков с P/N `Not Available`: 0.
- Контроллеры: 222 SATA/AHCI, 76 RAID, 35 BOSS, 16 HBA.
- Питание: 90 серверов используют `EnvironmentMetrics`, 21 — legacy fallback.
- Память: 2764 модуля с `SizeMiB`; `SizeMB` в новом разборе не используется.

## Что нельзя исправить в этом архиве

В `toExel.7z` нет HTTP/Redfish crawler, который выполнял GET-запросы и создал `redfish_full.json`. Поэтому здесь отсутствуют места, где возникали:

1. лишние GET к URI с `#fragment`;
2. `AttributeError: 'HttpClient' object has no attribute 'close'`.

Также в архиве отсутствует импортируемый проектом `search.py`. Из-за этого архив сам по себе не является полностью автономным. Для регрессионной проверки использовался временный test-only shim; в итоговый код он намеренно не добавлен.
