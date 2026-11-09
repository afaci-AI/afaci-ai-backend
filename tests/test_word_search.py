"""Word search and relevance rules: no database connection is required."""

import importlib
import re
import sys
import unittest
from collections import Counter
from types import ModuleType
from unittest.mock import patch

from core.db.text_filters import (
    SEPARATOR_REGEX,
    SearchQuery,
    normalize_search_text,
    parse_search_query,
    relevance_sql,
    search_match_sql,
    tokens_sql,
)


async def unused_db():
    raise AssertionError("Word search tests must not connect to a database")


session_stub = ModuleType("core.db.session")
session_stub.get_db = unused_db
with patch.dict(sys.modules, {"core.db.session": session_stub}):
    table = importlib.import_module("api.v1.table")


def tokens(name):
    return [t for t in re.split(r"[\s \-‐‑–—]+", name.lower().replace("ё", "е")) if t]


def bucket(name, query):
    """Python model of the SQL rules: None — no match, 0..3 — relevance."""
    q = parse_search_query(query)
    if q is None:
        return None
    norm = normalize_search_text(name)
    contiguous = q.needle in norm
    toks = tokens(name)
    words = len(q.words) > 1 and all(
        sum(1 for t in toks if t.startswith(w)) >= times
        for w, times in Counter(q.words).items()
    )
    if not (contiguous or words):
        return None
    if norm == q.needle:
        return 0
    if norm.startswith(q.needle):
        return 1
    return 2 if contiguous else 3


def search(names, query):
    ranked = [(bucket(n, query), n) for n in names]
    return [n for b, n in sorted(x for x in ranked if x[0] is not None)]


CATALOG = [
    "Агар",
    "Агар пищевой",
    "Агар-агар",
    "Молоко коровье 3,2%-ной жирности",
    "Молоко сухое",
    "Перец болгарский красный",
    "Перец чёрный молотый",
    "Сухари панировочные",
]


class ParseChecks(unittest.TestCase):
    def test_words_are_normalized_and_joined(self):
        self.assertEqual(
            parse_search_query("  Чёрный   ПЕРЕЦ "),
            SearchQuery(needle="черныйперец", words=("черный", "перец")),
        )

    def test_dashes_are_ignored_inside_a_word(self):
        self.assertEqual(parse_search_query("Агар-агар").words, ("агарагар",))

    def test_empty_query_is_none(self):
        self.assertIsNone(parse_search_query(None))
        self.assertIsNone(parse_search_query("  \t "))


class RuleChecks(unittest.TestCase):
    def test_words_in_any_order_and_partial_words(self):
        for query in ("перец черный", "черный перец", "ПЕРЕЦ чер молот"):
            self.assertEqual(search(CATALOG, query), ["Перец чёрный молотый"], query)
        self.assertEqual(search(CATALOG, "молоко сух"), ["Молоко сухое"])
        self.assertEqual(search(CATALOG, "сух молоко"), ["Молоко сухое"])

    def test_one_matching_word_of_several_is_not_enough(self):
        self.assertEqual(search(CATALOG, "перец сухой"), [])

    def test_exact_before_prefix_before_inside_before_words(self):
        self.assertEqual(search(CATALOG, "агар"), ["Агар", "Агар пищевой", "Агар-агар"])
        self.assertEqual(
            search(CATALOG, "сух"), ["Сухари панировочные", "Молоко сухое"]
        )

    def test_space_and_dash_variants_return_the_same_set(self):
        forms = ["агар агар", "агарагар", "а гар аг ар", "Агар-агар"]
        results = {tuple(sorted(search(CATALOG, f))) for f in forms}
        self.assertEqual(results, {("Агар-агар",)})

    def test_repeated_word_needs_repeated_occurrence(self):
        self.assertNotIn("Агар", search(CATALOG, "агар агар"))
        self.assertNotIn("Агар пищевой", search(CATALOG, "агар агар"))


class SqlChecks(unittest.TestCase):
    def test_single_word_uses_only_the_contiguous_condition(self):
        clause, params = search_match_sql("n", "tk", parse_search_query("перец"), "q")
        self.assertNotIn("unnest", clause)
        self.assertEqual(params, {"q": "%перец%"})

    def test_several_words_add_token_prefix_conditions(self):
        clause, params = search_match_sql(
            "n", "tk", parse_search_query("черный перец"), "q"
        )
        self.assertEqual(clause.count("unnest(tk)"), 2)
        self.assertEqual(params["q_w0"], "черный%")
        self.assertEqual(params["q_w1"], "перец%")
        self.assertIn(">= 1", clause)

    def test_repeated_word_requires_two_tokens(self):
        clause, _ = search_match_sql("n", "tk", parse_search_query("агар агар"), "q")
        self.assertEqual(clause.count("unnest(tk)"), 1)
        self.assertIn(">= 2", clause)

    def test_like_wildcards_in_words_are_escaped(self):
        _, params = search_match_sql("n", "tk", parse_search_query("5% жир_"), "q")
        self.assertEqual(params["q"], "%5\\%жир\\_%")
        self.assertEqual(params["q_w0"], "5\\%%")
        self.assertEqual(params["q_w1"], "жир\\_%")

    def test_relevance_case_orders_four_levels(self):
        case, params = relevance_sql("n", parse_search_query("агар"), "q")
        self.assertLess(case.index("THEN 0"), case.index("THEN 1"))
        self.assertLess(case.index("THEN 1"), case.index("THEN 2"))
        self.assertTrue(case.endswith("ELSE 3 END"))
        self.assertEqual(params["q_eq"], "агар")

    def test_tokens_use_separator_regex_parameter(self):
        expr, params = tokens_sql("f", "k")
        self.assertIn("string_to_array", expr)
        self.assertEqual(params, {"k_sep": SEPARATOR_REGEX})

    def test_separator_regex_has_no_multibyte_character_class(self):
        # В БД с кодировкой SQL_ASCII класс [...] работает по байтам и ломает
        # кириллицу, поэтому многобайтовые разделители — только альтернативами.
        for cls in re.findall(r"\[[^\]]*\]", SEPARATOR_REGEX):
            self.assertTrue(cls.isascii(), cls)
        self.assertEqual(re.sub(SEPARATOR_REGEX, "|", "а-б\u00a0в  г—д"), "а|б|в|г|д")

    def test_relevance_goes_before_selected_sort_in_products_route(self):
        import inspect

        source = inspect.getsource(table.table_products)
        self.assertIn("ORDER BY {relevance_order}{sort_by} {sort_order}, p.id", source)


if __name__ == "__main__":
    unittest.main()
