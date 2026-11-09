"""
Нормализация текста для поиска по названиям (русские и кыргызские буквы).

БД работает в локали C (`LC_CTYPE=C`): `ILIKE` и `lower()` не сворачивают
регистр кириллицы. Поэтому одинаковая нормализация применяется и к запросу
(в Python), и к столбцу (в SQL через цепочку `replace()` по целым буквам).

Правила сопоставления:
  * регистр не учитывается (русские и кыргызские буквы, включая Ң, Ө, Ү);
  * `ё` и `Ё` приравниваются к `е`;
  * все пробельные символы и дефисы/тире игнорируются, в том числе внутри названия
    и запроса (`агар агар`, `агарагар` и «Агар-агар» совпадают).

Поиск по продуктам (`search_match_sql`) дополнительно понимает слова: запрос из
нескольких слов находит название, в котором каждое слово запроса — начало
отдельного слова названия, в любом порядке (`черный перец`, `молоко сух`).
Совпадение по части слов в выдачу не попадает; повторяющееся слово должно
встретиться в названии столько же раз.

Порядок выдачи (`relevance_sql`): точное название → название начинается с
запроса → запрос целиком (слитно) внутри названия → все слова в любом порядке.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

# Заглавные буквы русского и кыргызского алфавитов: А–Я, Ё и Ң, Ө, Ү.
_UPPER_CYRILLIC = (
    "АБВГДЕЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ" + "Ё" + "ҢӨҮ"  # Ң Ө Ү
)

# Пробельные символы, которые не влияют на сопоставление.
_WHITESPACE = (" ", "\t", "\n", "\r", " ", " ", " ")
# Дефисы и тире тоже не влияют на сопоставление («Агар-агар» = `агар агар`).
_DASHES = ("-", "‐", "‑", "–", "—")

# Замены регистра и `ё` (для SQL). Левые части не пересекаются, порядок не важен.
FOLD_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    *((ch, ch.lower()) for ch in _UPPER_CYRILLIC if ch != "Ё"),
    ("Ё", "е"),
    ("ё", "е"),
)
# Удаление пробельных символов и дефисов.
STRIP_REPLACEMENTS: tuple[tuple[str, str], ...] = tuple(
    (ch, "") for ch in (*_WHITESPACE, *_DASHES)
)
SQL_REPLACEMENTS = FOLD_REPLACEMENTS + STRIP_REPLACEMENTS

# Разделители слов в названии (регулярное выражение). Многобайтовые символы
# перечислены альтернативами, а не символьным классом: в БД с кодировкой
# SQL_ASCII класс работает по байтам и разрушил бы кириллицу.
SEPARATOR_REGEX = (
    "(?:[ \\t\\n\\r\\-]|" + "|".join((*_WHITESPACE[4:], *_DASHES[1:])) + ")+"
)


def normalize_search_text(value: str) -> str:
    """Приводит строку к форме, в которой выполняется сопоставление."""
    lowered = value.lower().replace("ё", "е")
    return "".join(ch for ch in lowered if not ch.isspace() and ch not in _DASHES)


def escape_like(value: str) -> str:
    """Экранирует спецсимволы LIKE (`\\`, `%`, `_`) для `LIKE ... ESCAPE '\\'`."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _replace_chain(
    expression: str, replacements: tuple[tuple[str, str], ...], prefix: str
) -> tuple[str, dict[str, str | int]]:
    params: dict[str, str | int] = {}
    for index, (src, dst) in enumerate(replacements):
        src_key, dst_key = f"{prefix}s{index}", f"{prefix}d{index}"
        expression = f"replace({expression}, :{src_key}, :{dst_key})"
        params[src_key] = src
        params[dst_key] = dst
    return expression, params


def fold_sql(column: str, prefix: str) -> tuple[str, dict[str, str | int]]:
    """Столбец без учёта регистра и `ё`, разделители слов сохраняются."""
    return _replace_chain(f"lower({column})", FOLD_REPLACEMENTS, f"{prefix}f")


def strip_sql(expression: str, prefix: str) -> tuple[str, dict[str, str | int]]:
    """Выражение без пробельных символов и дефисов."""
    return _replace_chain(expression, STRIP_REPLACEMENTS, f"{prefix}t")


def normalized_sql(column: str, prefix: str) -> tuple[str, dict[str, str | int]]:
    """
    SQL-выражение полной нормализации столбца и параметры для него.

    Значения замен передаются параметрами SQL, а не подставляются в текст.
    `prefix` делает имена параметров уникальными в пределах запроса.
    """
    folded, params = fold_sql(column, prefix)
    stripped, strip_params = strip_sql(folded, prefix)
    return stripped, params | strip_params


def tokens_sql(folded: str, key: str) -> tuple[str, dict[str, str | int]]:
    """Массив слов названия (по пробелам и дефисам) из выражения `fold_sql`."""
    expr = (
        f"string_to_array(btrim(regexp_replace({folded}, :{key}_sep, ' ', 'g')), ' ')"
    )
    return expr, {f"{key}_sep": SEPARATOR_REGEX}


@dataclass(frozen=True)
class SearchQuery:
    """Разобранный запрос: все слова слитно (`needle`) и отдельные слова."""

    needle: str
    words: tuple[str, ...]


def parse_search_query(value: str | None) -> SearchQuery | None:
    """Разбирает запрос; None, если после нормализации он пустой."""
    if value is None:
        return None
    words = tuple(w for w in (normalize_search_text(x) for x in value.split()) if w)
    if not words:
        return None
    return SearchQuery(needle="".join(words), words=words)


def search_match_sql(
    norm: str, tokens: str, query: SearchQuery, key: str
) -> tuple[str, dict[str, str | int]]:
    """
    Условие совпадения названия с запросом.

    `norm` — нормализованное название без пробелов (`normalized_sql`), `tokens` —
    массив слов названия (`tokens_sql`). Совпадает, если запрос слитно есть
    внутри названия, либо каждое слово запроса — начало слова названия, в любом
    порядке; повторяющееся слово должно встретиться столько же раз
    (`агар агар` не находит «Агар»).
    """
    params: dict[str, str | int] = {key: f"%{escape_like(query.needle)}%"}
    clause = f"{norm} LIKE :{key} ESCAPE '\\'"
    if len(query.words) > 1:
        parts = []
        for index, (word, times) in enumerate(Counter(query.words).items()):
            word_key = f"{key}_w{index}"
            params[word_key] = f"{escape_like(word)}%"
            parts.append(
                f"(SELECT count(*) FROM unnest({tokens}) AS tk(w) "
                f"WHERE tk.w LIKE :{word_key} ESCAPE '\\') >= {times}"
            )
        clause = f"({clause} OR ({' AND '.join(parts)}))"
    return clause, params


def relevance_sql(
    norm: str,
    query: SearchQuery,
    key: str,
    *,
    word_clause: str | None = None,
    near_param: str | None = None,
) -> tuple[str, dict[str, str | int]]:
    """
    CASE-выражение приоритета: 0 точное, 1 начало, 2 слитно внутри, 3 слова.

    С `word_clause` (условие совпадения по словам) и `near_param` (список
    идентификаторов с одной ошибкой) добавляются приоритеты нечёткого поиска:
    4 — одна ошибка, 5 — остальные (в выдачу они попадают только из списка
    нечётких совпадений). Идентификаторы сравниваются как текст.
    """
    params: dict[str, str | int] = {
        f"{key}_eq": query.needle,
        f"{key}_pre": f"{escape_like(query.needle)}%",
        f"{key}_in": f"%{escape_like(query.needle)}%",
    }
    tail = "ELSE 3 END"
    if word_clause and near_param:
        tail = (
            f"WHEN {word_clause} THEN 3 "
            f"WHEN CAST(p.id AS text) = ANY(CAST(:{near_param} AS text[])) THEN 4 "
            "ELSE 5 END"
        )
    case = (
        f"CASE WHEN {norm} = :{key}_eq THEN 0 "
        f"WHEN {norm} LIKE :{key}_pre ESCAPE '\\' THEN 1 "
        f"WHEN {norm} LIKE :{key}_in ESCAPE '\\' THEN 2 {tail}"
    )
    return case, params


def contains_clause(
    column: str, value: str, key: str
) -> tuple[str, dict[str, str | int]]:
    """
    Условие «нормализованный столбец содержит нормализованное значение».

    Подстрока без учёта регистра, `ё/е`, пробелов и дефисов (без разбора по
    словам). Возвращает (SQL-фрагмент, параметры) или ("", {}), если значение
    пустое после нормализации (например, из одних пробелов).
    """
    query = parse_search_query(value)
    if query is None:
        return "", {}
    expression, params = normalized_sql(column, f"{key}_")
    params[key] = f"%{escape_like(query.needle)}%"
    return f"{expression} LIKE :{key} ESCAPE '\\'", params
