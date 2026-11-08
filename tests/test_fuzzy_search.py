"""Typo-tolerant search rules: no database connection is required."""

import importlib
import sys
import unittest
from types import ModuleType
from unittest.mock import patch

from infrastructure.db.fuzzy_search import (
    UNIT,
    edit_distance,
    fuzzy_cost,
    fuzzy_matches,
    max_errors,
    name_words,
    word_cost,
)
from infrastructure.db.text_filters import parse_search_query, relevance_sql


async def unused_db():
    raise AssertionError("Fuzzy search tests must not connect to a database")


session_stub = ModuleType("infrastructure.db.session")
session_stub.get_db = unused_db
with patch.dict(sys.modules, {"infrastructure.db.session": session_stub}):
    importlib.import_module("api.v1.table")

PRODUCTS = [
    ("1", "Молоко"),
    ("2", "Молоко сухое"),
    ("3", "Перец чёрный молотый"),
    ("4", "Мясо птицы"),
    ("5", "Масло сливочное"),
    ("6", "Баранина"),
    ("7", "Агар-агар"),
    ("8", "Рис"),
    ("9", "Яблоко сорта «Апорт»"),
    ("10", "Морковь"),
]


def found(query):
    return fuzzy_matches(query, PRODUCTS)


def ids(query):
    near, far = found(query)
    return set(near + far)


class EditDistanceTests(unittest.TestCase):
    def test_operations_cost_one_error(self):
        self.assertEqual(edit_distance("перец", "перец"), 0)
        self.assertEqual(edit_distance("перец", "перц"), UNIT)  # удаление
        self.assertEqual(edit_distance("перец", "перрец"), UNIT)  # вставка
        self.assertEqual(edit_distance("перец", "пирец"), UNIT // 2)  # е/и на слух
        self.assertEqual(edit_distance("перец", "пекец"), UNIT)  # замена
        self.assertEqual(edit_distance("перец", "пеерц"), UNIT)  # перестановка

    def test_similar_sounding_vowel_costs_half(self):
        self.assertEqual(edit_distance("малако", "молоко"), UNIT)
        self.assertEqual(edit_distance("хлеп", "хлеб"), UNIT)

    def test_distance_counts_letters_not_bytes(self):
        # В БД SQL_ASCII удаление русской буквы стоило бы 2, здесь — 1 ошибка.
        self.assertEqual(edit_distance("молоко", "молко"), UNIT)

    def test_limit_does_not_change_results_within_budget(self):
        pairs = [
            ("малако", "молоко"),
            ("перец", "парец"),
            ("баронина", "баранина"),
            ("свежий", "свежие"),
            ("хлеб", "хлопковое"),
            ("пшено", "пшеничные"),
        ]
        for a, b in pairs:
            full = edit_distance(a, b)
            for limit in (0, UNIT // 2, UNIT, 2 * UNIT, 4 * UNIT):
                limited = edit_distance(a, b, limit)
                if full <= limit:
                    self.assertEqual(limited, full, (a, b, limit))
                else:
                    self.assertGreater(limited, limit, (a, b, limit))

    def test_allowed_errors_by_length(self):
        lengths = (1, 3, 4, 5, 8, 9, 12)
        self.assertEqual([max_errors(n) for n in lengths], [0, 0, 0, 1, 1, 2, 2])


class WordCostTests(unittest.TestCase):
    def test_prefix_is_exact(self):
        self.assertEqual(word_cost("мол", "молоко"), 0)

    def test_typo_in_word_and_in_incomplete_word(self):
        self.assertEqual(word_cost("малако", "молоко"), UNIT)
        self.assertEqual(word_cost("молак", "молоко"), UNIT // 2)
        self.assertEqual(word_cost("молока", "молоко"), UNIT // 2)

    def test_incomplete_word_allows_one_error_at_most(self):
        # `молоко` не должно находить «молотый» (две замены в начале слова).
        self.assertIsNone(word_cost("молоко", "молотый"))
        self.assertIsNone(word_cost("мулак", "молоко"))

    def test_short_words_do_not_expand(self):
        for word, token in (("рис", "рыс"), ("мяо", "мясо"), ("мука", "макароны")):
            self.assertIsNone(word_cost(word, token), word)

    def test_too_many_errors(self):
        self.assertIsNone(word_cost("барабан", "баранина"))
        self.assertIsNone(word_cost("пирожок", "перец"))


class FuzzyCostTests(unittest.TestCase):
    def test_each_word_takes_its_own_token(self):
        self.assertEqual(
            fuzzy_cost(("перец", "чирный"), name_words("Перец чёрный")), UNIT // 2
        )
        self.assertIsNone(fuzzy_cost(("малако", "малако"), name_words("Молоко")))

    def test_exact_name_costs_zero(self):
        self.assertEqual(fuzzy_cost(("молоко",), name_words("Молоко")), 0)

    def test_dashes_split_words(self):
        self.assertEqual(fuzzy_cost(("агор", "агар"), name_words("Агар-агар")), None)
        self.assertEqual(fuzzy_cost(("агарр", "агар"), name_words("Агар-агар")), UNIT)


class FuzzyMatchesTests(unittest.TestCase):
    def test_malako_finds_milk(self):
        near, far = found("малако")
        self.assertIn("1", near)
        self.assertIn("2", near)
        self.assertNotIn("4", near + far)  # Мясо птицы

    def test_near_and_far_lists(self):
        self.assertEqual(found("баронина"), (["6"], []))
        self.assertEqual(found("барониана"), ([], ["6"]))  # две ошибки

    def test_case_yo_and_multiple_words(self):
        self.assertIn("3", ids("ПЕРЕЦ ЧИРНЫЙ"))
        self.assertIn("3", ids("перец черный молатый"))

    def test_exact_matches_are_not_fuzzy(self):
        self.assertEqual(found("молоко"), ([], []))
        self.assertEqual(found("перец чёрный"), ([], []))

    def test_unrelated_word_with_common_start_is_not_found(self):
        self.assertNotIn("3", ids("молоко"))  # «молотый»
        self.assertNotIn("9", ids("молоко"))  # «Яблоко»
        self.assertNotIn("10", ids("молоко"))

    def test_short_and_meaningless_queries_stay_empty(self):
        for query in ("ри", "рис", "мяс", "мосо", "ы", "   ", "xyz", "кккк"):
            self.assertEqual(found(query), ([], []), query)

    def test_no_wide_expansion_for_long_nonsense(self):
        self.assertEqual(found("фывапролдж"), ([], []))
        self.assertEqual(found("аааааааа"), ([], []))

    def test_word_count_is_limited(self):
        self.assertEqual(fuzzy_matches("а б в г д е ж молако", PRODUCTS), ([], []))


class RelevanceSqlTests(unittest.TestCase):
    def test_plain_form_is_unchanged(self):
        case, _ = relevance_sql("n", parse_search_query("перец"), "q")
        self.assertTrue(case.endswith("ELSE 3 END"))
        self.assertNotIn("fz_near", case)

    def test_fuzzy_buckets_follow_word_bucket(self):
        case, _ = relevance_sql(
            "n",
            parse_search_query("малако"),
            "q",
            word_clause="W",
            near_param="fz_near",
        )
        self.assertLess(case.index("THEN 2"), case.index("WHEN W THEN 3"))
        self.assertLess(case.index("WHEN W THEN 3"), case.index("THEN 4"))
        self.assertTrue(case.endswith("ELSE 5 END"))


if __name__ == "__main__":
    unittest.main()
