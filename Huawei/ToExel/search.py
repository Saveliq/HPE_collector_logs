import re
from typing import Any, Optional, Tuple, Union, Sequence

Scalar = (str, bytes, int, float, bool)


def is_absent(data):
    """Physical absence only; failed, disabled and offline hardware still exists."""
    if not isinstance(data, dict):
        values = [data]
    else:
        status = data.get("Status") or {}
        oem = data.get("Oem") or {}
        vendor = oem.get("Huawei") or {}
        values = [data.get("State"), data.get("DIMMStatus"),
                  status.get("State") if isinstance(status, dict) else status,
                  vendor.get("DIMMStatus")]
    return any(re.sub(r"[\s_-]", "", str(value)).lower() in
               {"absent", "notpresent", "notinstalled", "empty", "removed"}
               for value in values)

def _normalize_pattern(pat: Optional[str], consonants_only: bool) -> Optional[str]:
    if pat is None:
        return None
    if not consonants_only:
        return pat
    # Убираем гласные aeiou (регистрозависимость обработаем при компиляции флагом)
    return re.sub(r"[aeiou]", "", pat, flags=re.IGNORECASE)

def _normalize_text(s: str, consonants_only: bool) -> str:
    if not consonants_only:
        return s
    return re.sub(r"[aeiou]", "", s, flags=re.IGNORECASE)

def _compile_optional(pat: Optional[str]) -> Optional[re.Pattern]:
    if not pat:
        return None
    try:
        return re.compile(pat, re.IGNORECASE)
    except re.error as e:
        raise ValueError(f"Invalid regex after normalization: {pat!r} — {e}")

def search_one(
    data: Union[dict, list],
    key_pattern: Optional[str] = None,
    value_pattern: Optional[str] = None,
    value_type: Optional[Union[type, Tuple[type, ...]]] = None,
    return_path: bool = False,
    consonants_only: bool = False,
    path_pattern: Optional[Union[str, Sequence[str]]] = None,
    path_require_all: bool = False,
) -> Optional[Union[Tuple[Tuple, Any], Any]]:
    """
    Поиск первого совпадения в вложенной структуре (dict/list).

    :param data: структура для поиска
    :param key_pattern: regex (исходный, с гласными) для ключей
    :param value_pattern: regex (исходный) для значений
    :param value_type: тип значения (или кортеж типов)
    :param return_path: True -> вернуть (path, value), False -> вернуть value
    :param consonants_only: True -> из паттернов и значений убрать гласные (aeiou) перед сравнением
    :param path_pattern: None | str | list[str] — regex(ы), которые должны встретиться в path
    :param path_require_all: если path_pattern список: все ли паттерны должны присутствовать (True) или хватит одного (False)
    :return: (path, value) или value или None
    """

    # Нормализуем паттерны (удаляем гласные внутри строки паттерна, если нужно),
    # затем компилируем. Если после нормализации паттерн пуст -> считаем, что он невалиден -> None.
    key_pat_norm = _normalize_pattern(key_pattern, consonants_only)
    value_pat_norm = _normalize_pattern(value_pattern, consonants_only)

    # path_pattern может быть строкой или последовательностью
    path_pats = None
    if path_pattern is not None:
        if isinstance(path_pattern, (str, bytes)):
            path_pats = [_normalize_pattern(str(path_pattern), consonants_only)]
        else:
            path_pats = [_normalize_pattern(str(p), consonants_only) for p in path_pattern]

    key_regex = _compile_optional(key_pat_norm)
    value_regex = _compile_optional(value_pat_norm)
    path_regexes = [r for r in (_compile_optional(p) for p in (path_pats or [])) if r is not None]

    value_filters_provided = (value_pattern is not None) or (value_type is not None)

    def value_matches(v: Any) -> bool:
        if not isinstance(v, Scalar):
            return False
        norm_v = _normalize_text(str(v), consonants_only)
        if value_regex and not value_regex.search(norm_v):
            return False
        if value_type and not isinstance(v, value_type):
            return False
        return True

    def path_matches(path: Tuple) -> bool:
        # если паттернов по пути нет — путь всегда проходит
        if not path_regexes:
            return True
        # для каждого элемента пути проверяем нормализованный текст
        found = []
        for rx in path_regexes:
            matched_any = False
            for p in path:
                if rx.search(_normalize_text(str(p), consonants_only)):
                    matched_any = True
                    break
            found.append(matched_any)
        # если требуется все — все True, иначе — хотя бы один True
        return all(found) if path_require_all else any(found)

    def walk(obj: Any, path: Tuple = ()):
        if isinstance(obj, dict):
            for k, v in obj.items():
                cur_path = path + (k,)

                # сначала проверяем путь — если путь не проходит, не углубляемся в эту ветку
                if not path_matches(cur_path):
                    # но важно: если путь не подходит сейчас, возможно внутри (глубже) появится нужный элемент,
                    # поэтому НЕ пропускаем полностью — мы должны позволить рекурсии углубляться,
                    # иначе запрет на путь на этом уровне сделает невозможным найти совпадение глубже.
                    # Решение: не отбрасываем рекурсию для dict/list значений — мы только пропускаем
                    # проверку ключа/значения, но всё равно рекурсивно переходим внутрь.
                    pass

                norm_k = _normalize_text(str(k), consonants_only)

                # Проверка ключа (только если путь проходит — иначе ключ в неподходящем пути не имеет смысла)
                if path_matches(cur_path) and key_regex and key_regex.search(norm_k):
                    # если заданы фильтры по значению — проверяем и их
                    if value_filters_provided:
                        if value_matches(v):
                            return cur_path, v
                    else:
                        # если фильтров нет — возвращаем сразу
                        return cur_path, v

                # Проверка значения (только если путь проходит)
                if (key_regex is None) and path_matches(cur_path) and value_filters_provided and value_matches(v):
                    return cur_path, v

                # Рекурсия в любом случае — чтобы не потерять потенциальные совпадения глубже
                if isinstance(v, (dict, list)):
                    res = walk(v, cur_path)
                    if res:
                        return res

        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                cur_path = path + (i,)

                if (key_regex is None) and path_matches(cur_path) and value_filters_provided and value_matches(item):
                    return cur_path, item

                if isinstance(item, (dict, list)):
                    res = walk(item, cur_path)
                    if res:
                        return res

        return None

    found = walk(data, ())
    if not found:
        return None
    path, val = found
    return val if not return_path else (path, val)



def stripJSON(json_data):
    if not type(json_data) is dict and not type(json_data) is set and not type(json_data) is list:
        return json_data.strip() if isinstance(json_data, str) else json_data
    if type(json_data) is list:
        for i in range(len(json_data)):
            json_data[i] = stripJSON(json_data[i])
    elif type(json_data) is dict:
        for key in json_data:
            json_data[key] = stripJSON(json_data[key])

    return json_data


# Huawei helpers: an enclosing chassis never inherits linked device identity.
from copy import deepcopy
from getFromJSON.getDiagnostics import canonical_resources, component_fields


def as_dict(value):
    return value if isinstance(value, dict) else {}


def as_list(value):
    return value if isinstance(value, list) else []


def huawei(node):
    return as_dict(as_dict(node.get("Oem")).get("Huawei"))


def first_value(*values):
    return next((value for value in values if value is not None and value != ""), None)


def identifier(*values):
    for value in values:
        if isinstance(value, str) and value.strip().lower() not in {
            "", "unknown", "n/a", "na", "none", "null", "notpresent", "absent", "0"
        }:
            return value.strip()
    return None


def scaled(value, factor):
    return value * factor if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def unique_components(nodes):
    """Collapse repeated resources/serials, never equal names or empty serials."""
    result, seen = [], set()
    for node in nodes:
        keys = []
        if node.get("PhysicalKey"):
            keys.append(("physical", node["PhysicalKey"]))
        if node.get("SourcePath"):
            keys.append(("path", node["SourcePath"]))
        serial = identifier(node.get("SerialNumber"))
        if serial:
            keys.append(("serial", serial.upper()))
        if any(key in seen for key in keys):
            continue
        seen.update(keys)
        result.append(node)
    return result


class Resources:
    def __init__(self, raw):
        self.data = canonical_resources(raw)
        self.system_path = self._root("Systems")
        self.chassis_path = self._root("Chassis")
        self.manager_path = self._root("Managers")

    def _root(self, collection):
        pattern = r"/redfish/v1/" + collection + r"/[^/#]+"
        return next((path for path, node in self.data.items()
                     if re.fullmatch(pattern, path) and "error" not in node), "")

    def resolve(self, reference):
        if isinstance(reference, str):
            reference = {"@odata.id": reference}
        reference = as_dict(reference)
        path = reference.get("@odata.id", "")
        base, _, fragment = path.partition("#")
        value = self.data.get(base.rstrip("/"), {})
        if fragment:
            try:
                for part in fragment.strip("/").split("/"):
                    part = part.replace("~1", "/").replace("~0", "~")
                    value = value[int(part)] if isinstance(value, list) else value[part]
            except (KeyError, IndexError, TypeError, ValueError):
                value = self.data.get(path, {})
        if "error" in as_dict(value):
            return {}
        return deepcopy(dict(reference, **as_dict(value)))

    def matching(self, pattern):
        return [self.resolve(dict(node, **{"@odata.id": node.get("@odata.id", path)}))
                for path, node in self.data.items() if re.fullmatch(pattern, path) and "error" not in node]

    def children(self, path, collection):
        return self.matching(re.escape(path + "/" + collection) + r"/[^/#]+") if path else []

    def component(self, node):
        result = deepcopy(node)
        result.update(component_fields(node))
        oem = huawei(node)
        for field in ("SerialNumber", "PartNumber"):
            result[field] = identifier(node.get(field), oem.get(field))
        result["SourcePath"] = node.get("@odata.id")
        return stripJSON(result)

    def installed(self, nodes, keep_absent=False):
        result = []
        for ref in nodes:
            node = self.resolve(ref)
            if ("error" in node or not any(k in node for k in ("Name", "Model", "Status")) or
                    (not keep_absent and is_absent(node))):
                continue
            result.append(self.component(node))
        return unique_components(result)

    def boards(self):
        # Keep LOM and motherboard views here so callers can reconcile them.
        return [self.component(node) for node in self.children(self.chassis_path, "Boards") if not is_absent(node)]

    def integrated_mainboard(self, board):
        """LOM may be a function of the motherboard with the same FRU serial."""
        serial = identifier(board.get("SerialNumber"))
        if board.get("DeviceType") != "NICCard" or not serial or board.get("Location") != "mainboard":
            return None
        return next((item for item in self.children(self.chassis_path, "Boards")
                     if item.get("DeviceType") == "MainBoard" and not is_absent(item) and
                     identifier(item.get("SerialNumber")) == serial), None)
