"""Search normalization regressions: no database connection is required."""

import importlib
import sys
import unittest
from types import ModuleType
from unittest.mock import patch
from uuid import UUID

from infrastructure.db.text_filters import (
    SQL_REPLACEMENTS,
    contains_clause,
    escape_like,
    normalize_search_text,
    normalized_sql,
)


async def unused_db():
    raise AssertionError("Search normalization tests must not connect to a database")


session_stub = ModuleType("infrastructure.db.session")
session_stub.get_db = unused_db
with patch.dict(sys.modules, {"infrastructure.db.session": session_stub}):
    table = importlib.import_module("api.v1.table")


def apply_sql_chain(value: str) -> str:
    """Python model of the SQL expression: lower() for ASCII, then replace()."""
    result = "".join(ch.lower() if ch.isascii() else ch for ch in value)
    for src, dst in SQL_REPLACEMENTS:
        result = result.replace(src, dst)
    return result


class NormalizeSearchTextChecks(unittest.TestCase):
    def test_case_variants_are_equal(self):
        variants = ["Агар", "агар", "АГАР", "аГаР", " агар "]
        self.assertEqual({normalize_search_text(v) for v in variants}, {"агар"})

    def test_yo_equals_ye(self):
        self.assertEqual(normalize_search_text("черный"), "черный")
        self.assertEqual(normalize_search_text("Чёрный"), "черный")
        self.assertEqual(normalize_search_text("ЧЁРНЫЙ"), "черный")

    def test_spaces_are_ignored_everywhere(self):
        variants = ["агар агар", "агарагар", "а гар аг ар", "агар агар"]
        self.assertEqual({normalize_search_text(v) for v in variants}, {"агарагар"})

    def test_kyrgyz_letters(self):
        self.assertEqual(normalize_search_text("ӨҮҢ өүң"), "өүңөүң")

    def test_whitespace_only_is_empty(self):
        self.assertEqual(normalize_search_text("  \t\n"), "")


class SqlChainChecks(unittest.TestCase):
    def test_sql_chain_matches_python_normalization(self):
        samples = [
            "Агар-агар",
            "Перец чёрный молотый",
            "ЁЖ",
            "ӨРҮК Ңоо",
            "Молоко  сухое",
            "Творог 5%-ной жирности",
            "ABC def",
        ]
        for sample in samples:
            self.assertEqual(
                apply_sql_chain(sample), normalize_search_text(sample), sample
            )

    def test_every_russian_and_kyrgyz_capital_is_covered(self):
        sources = {src for src, _ in SQL_REPLACEMENTS}
        capitals = [chr(c) for c in range(0x0410, 0x0430)] + [
            "Ё",
            "Ң",
            "Ө",
            "Ү",
        ]
        self.assertEqual([c for c in capitals if c not in sources], [])

    def test_source_fragments_do_not_overlap(self):
        sources = [src for src, _ in SQL_REPLACEMENTS]
        self.assertEqual(len(sources), len(set(sources)))

    def test_values_are_bind_parameters_not_sql_text(self):
        expression, params = normalized_sql("p.name", "x_")
        self.assertNotIn("А", expression)
        self.assertEqual(len(params), 2 * len(SQL_REPLACEMENTS))
        self.assertTrue(all(f":{key}" in expression for key in params))


class ContainsClauseChecks(unittest.TestCase):
    def test_empty_value_adds_no_clause(self):
        self.assertEqual(contains_clause("p.name", "   ", "k"), ("", {}))

    def test_like_wildcards_are_escaped(self):
        self.assertEqual(escape_like("100%_\\"), "100\\%\\_\\\\")
        _, params = contains_clause("p.name", "100%", "k")
        self.assertEqual(params["k"], "%100\\%%")

    def test_same_needle_for_all_spellings(self):
        needles = {
            contains_clause("p.name", value, "k")[1]["k"]
            for value in ("агар агар", "агарагар", "а гар аг ар", "АГАР АГАР")
        }
        self.assertEqual(needles, {"%агарагар%"})


class TableFiltersChecks(unittest.TestCase):
    def test_build_where_skips_blank_and_none(self):
        where, params = table._build_where({"p.name": "  ", "c.name": None})
        self.assertEqual((where, params), ("", {}))

    def test_build_where_combines_filters_with_unique_params(self):
        where, params = table._build_where({"c.name": "мясо", "p.name": "Баранина"})
        self.assertTrue(where.startswith("WHERE "))
        self.assertEqual(where.count(" AND "), 1)
        self.assertEqual(params["p0"], "%мясо%")
        self.assertEqual(params["p1"], "%баранина%")
        self.assertEqual(len(params), len(set(params)))

    def test_exact_ids_are_added_after_name_filters(self):
        category = UUID("11111111-1111-1111-1111-111111111111")
        params: dict = {}
        where = table._add_exact_ids(
            "WHERE x", params, {"p.category_id": category, "p.region_id": None}
        )
        self.assertEqual(where, "WHERE x AND p.category_id = CAST(:id0 AS uuid)")
        self.assertEqual(params, {"id0": str(category)})

    def test_exact_ids_without_name_filters_open_where(self):
        region = UUID("22222222-2222-2222-2222-222222222222")
        where = table._add_exact_ids("", {}, {"p.region_id": region})
        self.assertEqual(where, "WHERE p.region_id = CAST(:id0 AS uuid)")

    def test_exact_ids_none_keeps_where(self):
        self.assertEqual(table._add_exact_ids("WHERE x", {}, {"a": None}), "WHERE x")


if __name__ == "__main__":
    unittest.main()
