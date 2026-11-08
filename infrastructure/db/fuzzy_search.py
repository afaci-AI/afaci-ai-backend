"""
Поиск с опечатками по названиям продуктов.

Почему не в SQL. БД работает в локали C, контейнерная dev-БД ещё и в кодировке
`SQL_ASCII`: `pg_trgm` не видит кириллицу (`similarity('малако', 'молоко') = 0`),
а `levenshtein` считает по байтам (удаление русской буквы стоит 2, а не 1).
Поэтому похожие названия находятся в Python по символам, а в SQL передаётся
готовый список идентификаторов.

Правила. Стоимость считается в «половинках ошибки» (`UNIT` = одна ошибка):
  * вставка, удаление, замена буквы, перестановка двух соседних — 1 ошибка;
  * замена на созвучную гласную (а↔о, е↔и, и↔ы, е↔я, е↔э) — полошибки: так
    пишут на слух, `малако` для «молоко» — это одна ошибка, а не две;
  * бюджет слова запроса зависит от длины: до 4 букв — 0 ошибок (короткие
    запросы не расширяются случайными совпадениями), 5–8 букв — 1 ошибка,
    9 и больше — 2;
  * слово запроса сравнивается с целым словом названия (весь бюджет) и с его
    началом (не больше 1 ошибки), поэтому неполное слово с опечаткой (`молак`)
    тоже находит «Молоко»;
  * слова нормализуются как в `text_filters` (регистр, `ё` = `е`, дефисы и
    пробелы разделяют слова), каждое слово запроса занимает отдельное слово
    названия; название без ошибок (точное или по словам) здесь не учитывается:
    его уже нашёл основной поиск;
  * слитная форма без пробелов (`перецчерный`) нечётко не сравнивается.
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable
from functools import lru_cache

from infrastructure.db.text_filters import normalize_search_text

_SPLIT = re.compile(r"[\s\-‐‑–—]+")

# Больше слов запроса не разбираем: перебор сопоставлений растёт быстро.
MAX_FUZZY_WORDS = 6

# Одна ошибка в «половинках»: замена созвучной гласной стоит 1, остальное — 2.
UNIT = 2
_SOUND_PAIRS = frozenset(frozenset(pair) for pair in ("ао", "еи", "иы", "ея", "еэ"))


def max_errors(length: int) -> int:
    """Допустимое число ошибок для слова запроса длиной `length`."""
    if length <= 4:
        return 0
    return 1 if length <= 8 else 2


def _substitution(a: str, b: str) -> int:
    if a == b:
        return 0
    return 1 if frozenset((a, b)) in _SOUND_PAIRS else UNIT


def name_words(name: str) -> list[str]:
    """Слова названия в нормализованном виде (без регистра, `ё` = `е`)."""
    lowered = name.lower().replace("ё", "е")
    return [w for w in _SPLIT.split(lowered) if w]


def edit_distance(a: str, b: str, limit: int | None = None) -> int:
    """
    Расстояние Дамерау — Левенштейна в «половинках ошибки» (см. `UNIT`).

    Вставка, удаление и перестановка соседних букв стоят `UNIT`, замена
    созвучной гласной — половину, другая замена — `UNIT`. Если задан `limit`
    и расстояние заведомо больше, расчёт обрывается и возвращается `limit + 1`.
    """
    if a == b:
        return 0
    if limit is not None and abs(len(a) - len(b)) * UNIT > limit:
        return limit + 1
    rows = [[j * UNIT for j in range(len(b) + 1)]]
    for i, ca in enumerate(a, start=1):
        row = [i * UNIT]
        for j, cb in enumerate(b, start=1):
            value = min(
                rows[i - 1][j] + UNIT,
                row[j - 1] + UNIT,
                rows[i - 1][j - 1] + _substitution(ca, cb),
            )
            if i > 1 and j > 1 and ca == b[j - 2] and a[i - 2] == cb:
                value = min(value, rows[i - 2][j - 2] + UNIT)
            row.append(value)
        rows.append(row)
        # Следующие строки не могут стать меньше минимума двух последних.
        if limit is not None and i > 1 and min(row) > limit and min(rows[-2]) > limit:
            return limit + 1
    return rows[-1][-1]


@lru_cache(maxsize=200_000)
def word_cost(word: str, token: str) -> int | None:
    """
    Стоимость слова запроса относительно слова названия (в долях `UNIT`).

    0 — слово является началом `token`; None — больше допустимого бюджета.
    Для начала слова (неполное слово запроса) бюджет не больше одной ошибки:
    иначе длинные запросы находили бы чужие слова с общей приставкой.
    """
    if token.startswith(word):
        return 0
    budget = max_errors(len(word)) * UNIT
    if budget == 0:
        return None
    best = None
    full = edit_distance(word, token, budget)
    if full <= budget:
        best = full
    prefix_budget = min(budget, UNIT)
    slack = 1
    low = max(1, len(word) - slack)
    high = min(len(token), len(word) + slack)
    for size in range(low, high + 1):
        distance = edit_distance(word, token[:size], prefix_budget)
        if distance <= prefix_budget and (best is None or distance < best):
            best = distance
    return best


def fuzzy_cost(words: tuple[str, ...], tokens: list[str]) -> int | None:
    """
    Наименьшая суммарная стоимость (в долях `UNIT`) сопоставления слов запроса
    словам названия.

    Каждое слово запроса занимает отдельное слово названия. None — сопоставить
    нельзя. 0 означает совпадение без ошибок (основной поиск его уже нашёл).
    """
    if len(words) > MAX_FUZZY_WORDS or len(words) > len(tokens):
        return None
    costs = [[word_cost(w, t) for t in tokens] for w in words]

    def solve(index: int, used: int) -> int | None:
        if index == len(words):
            return 0
        best = None
        for position, cost in enumerate(costs[index]):
            if cost is None or used >> position & 1:
                continue
            rest = solve(index + 1, used | 1 << position)
            if rest is not None and (best is None or cost + rest < best):
                best = cost + rest
        return best

    return solve(0, 0)


def fuzzy_matches(
    query: str, products: Iterable[tuple[str, str]]
) -> tuple[list[str], list[str]]:
    """
    Идентификаторы продуктов с названием, похожим на запрос.

    `products` — пары (идентификатор, название). Возвращает два списка: не
    больше одной ошибки в сумме и больше. Названия без ошибок пропускаются.
    """
    words = tuple(w for w in (normalize_search_text(x) for x in query.split()) if w)
    if not words or all(max_errors(len(w)) == 0 for w in words):
        # Все слова слишком короткие: ошибки не допускаются, расширять нечем.
        return [], []
    by_name: dict[str, list[str]] = defaultdict(list)
    for product_id, name in products:
        by_name[name].append(product_id)
    near: list[str] = []
    far: list[str] = []
    for name, product_ids in by_name.items():
        cost = fuzzy_cost(words, name_words(name))
        if cost:
            (near if cost <= UNIT else far).extend(product_ids)
    return near, far
