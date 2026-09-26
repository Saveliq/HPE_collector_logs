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
        hpe = oem.get("Hpe") or oem.get("Hp") or {}
        values = [data.get("State"), data.get("DIMMStatus"),
                  status.get("State") if isinstance(status, dict) else status,
                  hpe.get("DIMMStatus")]
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


from getFromJSON.getDiagnostics import canonical_resources, component_fields

SYSTEM = "/redfish/v1/Systems/System.Embedded.1"
CHASSIS = "/redfish/v1/Chassis/System.Embedded.1"
MANAGER = "/redfish/v1/Managers/iDRAC.Embedded.1"


def _dict(value):
    return value if isinstance(value, dict) else {}


def _list(value):
    return value if isinstance(value, list) else []


def _first(*values):
    """Keep explicit zero/False, but ignore missing and empty string fields."""
    return next((v for v in values if v is not None and v != ""), None)


def _scaled(value, factor):
    return value * factor if isinstance(value, (int, float)) and not isinstance(value, bool) else None


class Resources:
    def __init__(self, raw):
        self.data = canonical_resources(raw)

    def resolve(self, reference):
        reference = _dict(reference)
        path = reference.get("@odata.id", "")
        base, _, fragment = path.partition("#")
        value = self.data.get(base.rstrip("/"), {})
        if fragment:
            try:
                for part in fragment.strip("/").split("/"):
                    part = part.replace("~1", "/").replace("~0", "~")
                    value = value[int(part)] if isinstance(value, list) else value[part]
            except (KeyError, IndexError, TypeError, ValueError):
                value = {}
        return dict(reference, **_dict(value))

    def matching(self, pattern):
        return [node for path, node in self.data.items()
                if re.fullmatch(pattern, path) and "error" not in node]

    def oem(self, node, name):
        return self.resolve(_dict(_dict(node.get("Oem")).get("Dell")).get(name))

    def component(self, node, enrich_pcie=False):
        """Only controllers/adapters may use their linked PCIe identity."""
        result = dict(node, **component_fields(node))
        if not enrich_pcie:
            return result
        links = _dict(node.get("Links"))
        devices = [self.resolve(ref) for ref in _list(links.get("PCIeDevices"))]
        for ref in _list(links.get("PCIeFunctions")):
            function = self.resolve(ref)
            device_ref = _dict(function.get("Links")).get("PCIeDevice")
            if not device_ref:
                path = _dict(ref).get("@odata.id", "")
                device_ref = {"@odata.id": path.split("/PCIeFunctions/", 1)[0]}
            devices.append(self.resolve(device_ref))
        for device in devices:
            for field in ("PartNumber", "SerialNumber"):
                result[field] = _first(result.get(field), device.get(field))
        return result


def _installed(resources, nodes, keep_absent=False, enrich_pcie=False):
    result = []
    seen = set()
    for node in nodes:
        node = resources.resolve(node)
        if (not node or "error" in node or
                not any(key in node for key in ("Name", "Model", "Status", "SerialNumber")) or
                (not keep_absent and is_absent(node))):
            continue
        # The same device can be returned through a collection and a direct URL.
        key = node.get("@odata.id")
        if key and key in seen:
            continue
        if key:
            seen.add(key)
        result.append(resources.component(node, enrich_pcie=enrich_pcie))
    return result


