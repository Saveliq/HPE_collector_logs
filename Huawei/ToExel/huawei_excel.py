"""Huawei/xFusion Redfish -> Excel in the five-sheet Dell audit layout.

The included layout_template.xlsx contains ONLY formatting sampled from the
user-provided Dell report. Its server inventory and identifiers are NOT included.

Only openpyxl is needed. The public export(servers, filename) API is unchanged.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from copy import copy
from pathlib import Path
import math

from openpyxl import load_workbook
from openpyxl.formatting.rule import CellIsRule
from openpyxl.styles import PatternFill
from openpyxl.worksheet.table import Table, TableStyleInfo
from openpyxl.utils import get_column_letter
from huawei_parser import valid

TEMPLATE = Path(__file__).with_name('layout_template.xlsx')
SHEET_NAMES = ['Аудит', 'Группировка_PN', 'Сводка_серверов', 'Микрокоды', 'Health']
BAD_HEALTH = {'critical', 'warning', 'failed', 'degraded', 'noncritical', 'fatal', 'error', 'unhealthy'}
BAD_STATE = {'critical', 'failed', 'degraded', 'disabled', 'unavailableoffline', 'standbyoffline'}


def text(v):
    """Display values without making up IDs, and without injection of formulas."""
    if v is None:
        return None
    if isinstance(v, float) and not math.isfinite(v):
        return None
    if isinstance(v, (str, int, float, bool)):
        return v[:32767] if isinstance(v, str) else v
    return str(v)[:32767]


def set_cell(ws, row, col, value, prototype=None):
    cell = ws.cell(row, col)
    if prototype is not None:
        cell._style = copy(prototype._style)
    v = text(value)
    if v is not None:
        cell.value = v
        if isinstance(v, str) and v.startswith('='):
            cell.data_type = 's'
    else:
        cell.value = None
    return cell


def append_row(ws, values, prototypes=None):
    r = ws.max_row + 1
    for c, v in enumerate(values, 1):
        set_cell(ws, r, c, v, prototypes[c - 1] if prototypes else None)
    return r


def write_row(ws, row, values, prototypes=None):
    for c, v in enumerate(values, 1):
        set_cell(ws, row, c, v, prototypes[c - 1] if prototypes else None)


def style_row(ws, row, values, prototype):
    # Prototype is a snapshot of cells, so styles remain stable after overwriting.
    write_row(ws, row, values, prototype)


def clone_style_cells(ws, row, width):
    return [copy(ws.cell(row, c)._style) for c in range(1, width + 1)]


def write_style_row(ws, row, values, styles):
    for c, v in enumerate(values, 1):
        cell = set_cell(ws, row, c, v)
        if c <= len(styles):
            cell._style = copy(styles[c - 1])


def hardware_name(component):
    cat = component['Category']
    return {'RAID/HBA': 'RAID контроллер', 'PCIe устройство': 'PCIe устройство',
            'Сетевая PCIe карта': 'Сетевой адаптер PCIe'}.get(cat, cat)


def description(c):
    details = c.get('Info') or {}
    if details and any(v is not None and v != '' for v in details.values()):
        return repr({key: value for key, value in details.items() if value is not None and value != ''})
    return c.get('Model') or c.get('Name')


def comment(c):
    d = {}
    for key, value in [('Model', c.get('Model')), ('Manufacturer', c.get('Manufacturer')),
                       ('Location', c.get('Location'))]:
        if valid(value):
            d[key] = value
    # The Redfish resource pointer supports traceability while retaining Dell's
    # dedicated 'Комментарий' column, with no extra columns.
    if c.get('SourcePath'):
        d['Redfish'] = c['SourcePath']
    return repr(d) if d else None


def is_bad(value):
    return str(value or '').replace('_', '').replace(' ', '').lower() in BAD_HEALTH | BAD_STATE


def hardware_issue(s, c=None):
    x = c or {'Health': s.get('ServerHealth'), 'HealthRollup': s.get('ServerHealthRollup'),
              'State': s.get('ServerState')}
    return any(is_bad(x.get(k)) for k in ('Health', 'HealthRollup')) or str(x.get('State') or '').lower() in {'failed', 'degraded', 'critical'}


def group_by_model_version(servers, field_keys):
    groups = defaultdict(list)
    totals = Counter(s.get('Model') or '' for s in servers)
    for s in servers:
        keys = tuple(s.get(k) or '' for k in field_keys)
        groups[(s.get('Model') or '', *keys)].append(s.get('SerialNumber') or '')
    return totals, sorted(groups.items(), key=lambda kv: tuple(str(x) for x in kv[0]))


def _group_psu_redundancy(server):
    """Redundancy validity requires explicit status, not just a named Mode."""
    reds = server.get('Redundancy') or []
    if not reds:
        return None
    for red in reds:
        stat = red.get('Status') or {}
        if stat.get('Health') in ('Critical', 'Warning'):
            return 'Yes'
    return None


def psu_mode_string(server):
    """Unambiguous per-PSU actual ActiveStandby values from Redfish."""
    return '; '.join(f'{x["Name"]}: {x["Mode"]}' for x in server.get('PSUModes', [])) or None


def power_capping_string(server):
    """Render OEM activation and its limit without conflating unset with False."""
    active = server.get('PowerCappingActivated')
    limit = server.get('PowerCappingLimitWatts')
    if active is True:
        return f'Enabled ({limit} Вт)' if valid(limit) else 'Enabled'
    if active is False:
        return 'Disabled'
    if valid(limit):
        return f'Лимит {limit} Вт (активация не указана)'
    return None


def expected_redundancy_string(server):
    """Display the target mode plus the exact Redfish Redundancy member ref."""
    ref = server.get('ExpectedRedundancy')
    if not valid(ref):
        return None
    mode = server.get('ExpectedRedundancyMode')
    # A stray/unresolved reference is shown verbatim, never guessed.
    return f'{mode} ({ref.split("#/")[-1]})' if valid(mode) and '#/' in ref else ref


GREEN = PatternFill(fill_type='solid', fgColor='FFC6EFCE')
RED = PatternFill(fill_type='solid', fgColor='FFFFC7CE')
YELLOW = PatternFill(fill_type='solid', fgColor='FFFFEB9C')
NO_FILL = PatternFill(fill_type=None)


def mark_status(ws, row, column):
    """Color *actual* cell values; never leave a Critical cell green.

    The Dell template pre-fills I/J server and component rows green.  Merely
    adding conditional formatting doesn't reliably override that in every
    spreadsheet viewer.  Static fills make the saved workbook correct too.
    """
    cell=ws.cell(row, column)
    state=str(cell.value or '').strip().lower().replace('_','').replace(' ','')
    if state in BAD_HEALTH or state in BAD_STATE:
        cell.fill = YELLOW if state in {'warning','noncritical','degraded'} else RED
    elif state in {'ok','enabled','healthy','normal','standbyspare','online'}:
        cell.fill = GREEN
    else:
        cell.fill = NO_FILL


def export(servers, filename):
    if not TEMPLATE.is_file():
        raise FileNotFoundError(f'Отсутствует шаблон Excel: {TEMPLATE}')
    wb = load_workbook(TEMPLATE)
    assert wb.sheetnames == SHEET_NAMES
    audit = wb['Аудит']
    pn = wb['Группировка_PN']
    summary = wb['Сводка_серверов']
    firmware = wb['Микрокоды']
    health = wb['Health']

    audit_server_style = clone_style_cells(audit, 2, 18)
    audit_component_style = clone_style_cells(audit, 3, 18)
    sum_head_style = clone_style_cells(summary, 6, 6)
    sum_body_style = clone_style_cells(summary, 7, 6)
    fw_body_style = clone_style_cells(firmware, 2, 6)
    health_body_style = clone_style_cells(health, 2, 12)
    # The template is intentionally a skeleton: erase all reserved example rows.
    for ws, start, end in [(audit, 2, 3), (pn, 2, 3), (firmware, 2, 2), (health, 2, 2)]:
        for r in range(start, end + 1):
            for cell in ws[r]:
                cell.value = None
    for row in (29, 30, 31, 49, 50, 51):
        for cell in summary[row]:
            cell.value = None

    fwc = Counter()
    fwservers = defaultdict(set)
    grouping_count = 0
    health_count = 0
    nr_audit = 2
    nr_pn = 1

    for idx, s in enumerate(servers, 1):
        server_sn = s.get('SerialNumber')
        health_sn_written = False
        model = s.get('Model')
        bios = s.get('BiosVersion')
        bmc = s.get('iBMCVersion')
        server_row = [
            idx, server_sn, s.get('PartNumber'), model, None, None, None,
            '; '.join(f'{key}: {val}' for key, val in [('BIOS', bios), ('iBMC', bmc)] if valid(val)) or None,
            s.get('ServerState'), s.get('ServerHealth'), s.get('ServerHealthRollup'),
            s.get('MemoryHealth'), s.get('CustomPowerPolicy'), s.get('PowerSaving'),
            s.get('PowerConsumedWatts'), psu_mode_string(s),
            power_capping_string(s), expected_redundancy_string(s),
        ]
        write_style_row(audit, nr_audit, server_row, audit_server_style)
        for col in range(9,13):
            mark_status(audit, nr_audit, col)
        if nr_audit != 2:
            audit.row_dimensions[nr_audit].height = audit.row_dimensions[2].height
        nr_audit += 1

        pn_counter = Counter()
        pn_descr = {}
        for c in s.get('Components', []):
            cat = hardware_name(c)
            info = c.get('Info') or {}
            component_row = [
                None, c.get('SerialNumber'), c.get('PartNumber'), cat,
                None, description(c), comment(c), c.get('FirmwareVersion'),
                c.get('State'), c.get('Health'), c.get('HealthRollup'),
                c.get('Health') if c.get('Category') == 'Память' else None,
                None, None, None, None, None, None,
            ]
            write_style_row(audit, nr_audit, component_row, audit_component_style)
            for col in range(9,13):
                mark_status(audit, nr_audit, col)
            nr_audit += 1
            pnkey = c.get('PartNumber') if valid(c.get('PartNumber')) else f'UNKNOWN_PN::{cat.replace(" ", "_")}'
            groupkey = (str(pnkey), cat)
            pn_counter[groupkey] += 1
            pn_descr.setdefault(groupkey, description(c))
            if hardware_issue(s, c):
                row = [server_sn if not health_sn_written else None, model,
                       cat, c.get('PartNumber'), c.get('SerialNumber'),
                       c.get('State'), c.get('Health'), c.get('FirmwareVersion'),
                       c.get('HealthRollup'), c.get('Model') or c.get('Name'),
                       c.get('SourcePath'), s.get('SourceFile')]
                write_style_row(health, 2 + health_count, row, health_body_style)
                for col in (6,7,9):
                    mark_status(health, 2 + health_count, col)
                health_count += 1
                health_sn_written = True
            if valid(c.get('FirmwareVersion')):
                label = cat
                identity = f'{c.get("Model") or c.get("Name") or cat} / {c.get("PartNumber") or "P/N не указан"}'
                key = (label, identity, str(c['FirmwareVersion']), 'Текущая')
                fwc[key] += 1
                fwservers[key].add(server_sn)

        # Exactly like the sample: two empty lines separate server blocks.
        if idx < len(servers):
            nr_audit += 2

        # Like Audit B<server-row>: the server S/N appears on its own line,
        # above the component list, exactly once in each grouping block.
        write_row(pn, nr_pn, ['S/N сервера', server_sn, 'Модель', model])
        nr_pn += 1
        write_row(pn, nr_pn, ['P/N', 'Компонент', 'Количество', 'Описание (пример)'])
        nr_pn += 1
        for (part, category), count in sorted(pn_counter.items(), key=lambda e: (-e[1], e[0][0], e[0][1])):
            write_row(pn, nr_pn, [part, category, count, pn_descr[(part, category)]])
            nr_pn += 1
            grouping_count += 1
        if idx < len(servers):
            nr_pn += 1

        if hardware_issue(s):
            row = [server_sn if not health_sn_written else None, model, 'Сервер', s.get('PartNumber'), server_sn,
                   s.get('ServerState'), s.get('ServerHealth'),
                   '; '.join(f'{key}: {value}' for key, value in [('BIOS', bios), ('iBMC', bmc)] if valid(value)) or None,
                   s.get('ServerHealthRollup'), model, s.get('SystemPath'), s.get('SourceFile')]
            write_style_row(health, 2 + health_count, row, health_body_style)
            for col in (6,7,9):
                mark_status(health, 2 + health_count, col)
            health_count += 1
            health_sn_written = True

        for f in s.get('FirmwareInventory', []):
            if not valid(f.get('Version')):
                continue
            role = f.get('Role') or 'Current'
            role_label = {'Current': 'Текущая', 'Active': 'Текущая',
                          'Backup': 'Резервная', 'Previous': 'Previous',
                          'Available': 'Доступная'}.get(role, role)
            key = ('FirmwareInventory', str(f.get('Name') or ''), str(f['Version']), role_label)
            fwc[key] += 1
            fwservers[key].add(server_sn)

    # Conditional rules also cover future manual cell edits in Excel.
    for col in 'IJKL':
        for keyword, color in [('Critical', 'FFFFC7CE'), ('Warning', 'FFFFEB9C')]:
            audit.conditional_formatting.add(
                f'{col}2:{col}{max(2,nr_audit - 1)}',
                CellIsRule(operator='equal', formula=[f'"{keyword}"'], fill=PatternFill('solid', fgColor=color)))

    # Copy precise reference widths; summary KPI and multi-section layout.
    summary['A1']='Всего серверов'
    summary['B1']='Моделей'
    summary['C1']='Health != OK'
    summary['D1']='Версий BIOS'
    summary['E1']='Версий iBMC'
    summary['A2']=len(servers)
    summary['B2']=len(set(s.get('Model') for s in servers))
    summary['C2']=sum(hardware_issue(s) or any(hardware_issue(s, c) for c in s.get('Components', [])) for s in servers)
    summary['D2']=len(set(str(s['BiosVersion']) for s in servers if valid(s.get('BiosVersion'))))
    summary['E2']=len(set(str(s['iBMCVersion']) for s in servers if valid(s.get('iBMCVersion'))))
    summary['A3']='Health != OK: серверы с отклонениями Health/HealthRollup у сервера или компонента.'
    summary['A5']='Модели и комбинации BIOS + iBMC'
    section_defs = [
        (['Модель сервера', 'BIOS', 'iBMC', 'Кол-во серверов', '% от модели', 'Service Tag / S/N серверов'],
         ('BiosVersion','iBMCVersion'), 'SummaryVersions'),
        (['Модель сервера', 'BIOS', 'Кол-во серверов', 'Серверов в модели', '% от модели', 'Service Tag / S/N серверов'],
         ('BiosVersion',), 'SummaryBIOS'),
        (['Модель сервера', 'iBMC', 'Кол-во серверов', 'Серверов в модели', '% от модели', 'Service Tag / S/N серверов'],
         ('iBMCVersion',), 'SummaryiBMC')]
    current_header = 6
    for sect_idx, (heads, keys, tablename) in enumerate(section_defs):
        if sect_idx > 0:
            title_row = current_header - 1
            title = 'Независимая сводка BIOS' if sect_idx == 1 else 'Независимая сводка iBMC'
            summary.cell(title_row, 1).value=title
            summary.cell(title_row, 1).font=copy(summary['A5'].font)
        write_style_row(summary, current_header, heads, sum_head_style)
        totals, groups = group_by_model_version(servers, keys)
        for i, (group_key, serials) in enumerate(groups, current_header + 1):
            model, *versions = group_key
            if sect_idx == 0:
                row = [model, *versions, len(serials), len(serials)/totals[model] if totals[model] else 0,
                       ', '.join(sorted(str(sn) for sn in serials if sn))]
            else:
                row = [model, versions[0], len(serials), totals[model],
                       len(serials)/totals[model] if totals[model] else 0,
                       ', '.join(sorted(str(sn) for sn in serials if sn))]
            write_style_row(summary, i, row, sum_body_style)
            summary.cell(i, 5).number_format='0.0%'
            summary.row_dimensions[i].height = 30
        end_row = current_header + len(groups)
        if groups and sect_idx > 0:
            table = Table(displayName=tablename, ref=f'A{current_header}:F{end_row}')
            table.tableStyleInfo=TableStyleInfo(name=None, showFirstColumn=False, showLastColumn=False, showRowStripes=False, showColumnStripes=False)
            summary.add_table(table)
        if sect_idx == 0:
            summary.auto_filter.ref = f'A{current_header}:F{end_row}'
        current_header = end_row + 4

    # Microcode summary: one row per firmware, model, hardware P/N and role.
    for idx, (key, count) in enumerate(sorted(fwc.items()), 2):
        cat, identifier, version, role = key
        write_style_row(firmware, idx, [cat, identifier, version, count,
                                         len(fwservers[key]), role], fw_body_style)
        firmware.row_dimensions[idx].height=30
    firmware.auto_filter.ref=f'A1:F{max(1,1+len(fwc))}'
    health.auto_filter.ref=f'A1:L{max(1,1+health_count)}'
    # Unformatted PN list by request: keep content, block separators and widths.
    # This also removes any styles retained in the shipped template.
    for row in pn:
        for cell in row:
            cell._style = None
    pn.conditional_formatting._cf_rules.clear()
    audit.auto_filter.ref = None
    output=Path(filename)
    output.parent.mkdir(parents=True,exist_ok=True)
    wb.save(output)
    wb.close()
    return {'Серверы': len(servers), 'Компоненты': sum(len(s.get('Components',[])) for s in servers),
            'Прошивки':sum(len(s.get('FirmwareInventory',[])) for s in servers),
            'Проблемы':health_count, 'Аудит':nr_audit-1,
            'Группировка_PN':grouping_count, 'Микрокоды':len(fwc)}
