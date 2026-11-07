"""
Нормализация текста для поиска по названиям (русские и кыргызские буквы).

БД работает в локали C (`LC_CTYPE=C`): `ILIKE` и `lower()` не сворачивают
регистр кириллицы. Поэтому одинаковая нормализация применяется и к запросу
(в Python), и к столбцу (в SQL через цепочку `replace()` по целым буквам).

Правила сопоставления:
  * регистр не учитывается (русские и кыргызские буквы, включая Ң, Ө, Ү);
  * `ё` и `Ё` приравниваются к `е`;
  * все пробельные символы игнорируются, в том числе внутри названия и запроса.
"""

from __future__ import annotations

# Заглавные буквы русского и кыргызского алфавитов: А–Я, Ё и Ң, Ө, Ү.
_UPPER_CYRILLIC = (
    "АБВГДЕЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ" + "Ё" + "ҢӨҮ"  # Ң Ө Ү
)

# Пробельные символы, которые не влияют на сопоставление.
_WHITESPACE = (" ", "\t", "\n", "\r", " ", " ", " ")

# (что заменить, на что) для SQL. Порядок не важен: левые части не пересекаются.
SQL_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    *((ch, ch.lower()) for ch in _UPPER_CYRILLIC if ch != "Ё"),
    ("Ё", "е"),
    ("ё", "е"),
    *((ws, "") for ws in _WHITESPACE),
)


def normalize_search_text(value: str) -> str:
    """Приводит строку к форме, в которой выполняется сопоставление."""
    lowered = value.lower().replace("ё", "е")
    return "".join(ch for ch in lowered if not ch.isspace())


def escape_like(value: str) -> str:
    """Экранирует спецсимволы LIKE (`\\`, `%`, `_`) для `LIKE ... ESCAPE '\\'`."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def normalized_sql(column: str, prefix: str) -> tuple[str, dict[str, str]]:
    """
    SQL-выражение нормализации столбца и параметры для него.

    Значения замен передаются параметрами SQL, а не подставляются в текст.
    `prefix` делает имена параметров уникальными в пределах запроса.
    """
    expression = f"lower({column})"
    params: dict[str, str] = {}
    for index, (src, dst) in enumerate(SQL_REPLACEMENTS):
        src_key, dst_key = f"{prefix}s{index}", f"{prefix}d{index}"
        expression = f"replace({expression}, :{src_key}, :{dst_key})"
        params[src_key] = src
        params[dst_key] = dst
    return expression, params


def contains_clause(column: str, value: str, key: str) -> tuple[str, dict[str, str]]:
    """
    Условие «нормализованный столбец содержит нормализованное значение».

    Возвращает (SQL-фрагмент, параметры) или ("", {}), если значение пустое
    после нормализации (например, из одних пробелов).
    """
    needle = normalize_search_text(value)
    if not needle:
        return "", {}
    expression, params = normalized_sql(column, f"{key}_")
    params[key] = f"%{escape_like(needle)}%"
    return f"{expression} LIKE :{key} ESCAPE '\\'", params
