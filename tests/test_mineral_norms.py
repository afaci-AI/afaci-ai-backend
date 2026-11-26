"""Нормы минералов: значения миграции по таблицам МР, перевод единиц и строки блока."""

import importlib.util
import math
import unittest
from pathlib import Path

from features.norms.domain.daily_norms import (
    NORM_ORDER,
    NORMS_INFO,
    build_class_rows,
    convert_amount,
    mineral_norm_rows,
)
from features.norms.domain.records import CompositionEntry, DailyNorm

MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "b2c3d4e5f6a8_add_mineral_daily_norms.py"
)

# МР 2.3.1.0253-21, табл. 12 (мужчины) и 17 (женщины), «старше 18 лет»:
# (единица, мужчины, женщины). Адекватные уровни — табл. 13 и 18.
TABLES = {
    "Ca": ("мг", 1000, 1000),
    "P": ("мг", 700, 700),
    "Mg": ("мг", 420, 420),
    "K": ("мг", 3500, 3500),
    "Na": ("мг", 1300, 1300),
    "Fe": ("мг", 10, 18),
    "Zn": ("мг", 12, 12),
    "Cu": ("мг", 1.0, 1.0),
    "Mn": ("мг", 2.0, 2.0),
    "Se": ("мкг", 70, 55),
    "I": ("мкг", 150, 150),
    "Cr": ("мкг", 40, 40),
}
ADEQUATE = {"Co": ("мкг", 10), "V": ("мкг", 15)}
# Минералы базы без нормы в документе.
WITHOUT_NORM = ("Al", "B", "Li", "Ni", "Sn")


def load_migration():
    spec = importlib.util.spec_from_file_location("mineral_norms", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def half_up(value: float) -> float:
    return math.floor(value + 0.5)


class SeededValues(unittest.TestCase):
    def setUp(self):
        self.norms = {norm["key"]: norm for norm in load_migration().NORMS}

    def test_norms_are_average_of_men_and_women_rounded(self):
        for key, (unit, men, women) in TABLES.items():
            with self.subTest(key=key):
                norm = self.norms[key]
                average = (men + women) / 2
                expected = average if average < 10 else half_up(average)
                self.assertEqual(norm["unit"], unit)
                self.assertEqual(norm["value"], expected)
                self.assertEqual(norm["kind"], "norm")

    def test_iron_and_selenium_explain_averaging(self):
        self.assertEqual(self.norms["Fe"]["value"], 14.0)
        self.assertIn("10 мг", self.norms["Fe"]["basis"])
        self.assertEqual(self.norms["Se"]["value"], 63.0)
        self.assertIn("62,5", self.norms["Se"]["basis"])

    def test_calcium_is_for_adults_under_65(self):
        self.assertEqual(self.norms["Ca"]["value"], 1000.0)
        self.assertIn("1200 мг", self.norms["Ca"]["basis"])

    def test_adequate_levels_are_marked(self):
        for key, (unit, value) in ADEQUATE.items():
            with self.subTest(key=key):
                self.assertEqual(self.norms[key]["kind"], "adequate")
                self.assertEqual(self.norms[key]["unit"], unit)
                self.assertEqual(self.norms[key]["value"], value)

    def test_minerals_without_norm_get_no_value(self):
        for key in WITHOUT_NORM:
            self.assertNotIn(key, self.norms)

    def test_keys_do_not_clash_with_macro(self):
        self.assertFalse(set(self.norms) & set(NORM_ORDER))

    def test_info_explains_minerals(self):
        text = " ".join(NORMS_INFO["paragraphs"])
        self.assertIn("железо 14 мг", text)
        self.assertIn("адекватные уровни", text)
        self.assertIn("1 мг = 1000 мкг", text)


class Units(unittest.TestCase):
    def test_milligrams_to_micrograms(self):
        self.assertAlmostEqual(convert_amount(0.145, "мг", "мкг"), 145.0)

    def test_same_unit_and_missing_value_are_kept(self):
        self.assertEqual(convert_amount(2.5, "мг", "мг"), 2.5)
        self.assertIsNone(convert_amount(None, "мг", "мкг"))

    def test_unknown_conversion_is_refused(self):
        with self.assertRaises(ValueError):
            convert_amount(1.0, "%", "мг")


NORMS = (
    DailyNorm(key="Fe", unit="мг", value=14.0, source_id="s"),
    DailyNorm(key="Se", unit="мкг", value=63.0, source_id="s"),
    DailyNorm(key="Co", unit="мкг", value=10.0, kind="adequate"),
    DailyNorm(key="energy", unit="ккал", value=2602.0),
)


def entries(*rows):
    return [CompositionEntry.of(row) for row in rows]


class Rows(unittest.TestCase):
    def test_share_in_norm_unit(self):
        rows = build_class_rows(
            entries(
                {"name": "Fe", "unit": "мг/100г", "amount": 7.0},
                {"name": "Se", "unit": "мг/100г", "amount": 0.0315},
            ),
            list(NORMS),
        )
        fe, se = rows
        self.assertEqual((fe["unit"], fe["percent"]), ("мг", 50.0))
        self.assertEqual(se["unit"], "мкг")
        self.assertAlmostEqual(se["amount"], 31.5)
        self.assertEqual(se["percent"], 50.0)
        self.assertEqual(se["kind"], "norm")

    def test_nutrient_without_unit_does_not_break_rows(self):
        """Нутриент без единицы в справочнике: строка без доли, а не 500."""
        fe, se = build_class_rows(
            entries(
                {"name": "Fe", "unit": None, "amount": 7.0},
                {"name": "Se", "unit": "%", "amount": 1.0},
            ),
            list(NORMS),
        )
        for row in (fe, se):
            self.assertIsNone(row["norm"])
            self.assertIsNone(row["percent"])
        self.assertEqual(fe["amount"], 7.0)

    def test_adequate_level_keeps_kind(self):
        (row,) = build_class_rows(
            entries({"name": "Co", "unit": "мг/100г", "amount": 0.002}), list(NORMS)
        )
        self.assertEqual(row["kind"], "adequate")
        self.assertEqual(row["percent"], 20.0)

    def test_mineral_without_norm(self):
        (row,) = build_class_rows(
            entries({"name": "Al", "unit": "мг/100г", "amount": 1.2}), list(NORMS)
        )
        self.assertIsNone(row["norm"])
        self.assertIsNone(row["kind"])
        self.assertEqual(row["unit"], "мг")

    def test_general_list_has_only_minerals_without_amount(self):
        rows = mineral_norm_rows(list(NORMS))
        self.assertEqual([row["key"] for row in rows], ["Fe", "Se", "Co"])
        self.assertTrue(all(row["amount"] is None for row in rows))
        self.assertTrue(all(row["percent"] is None for row in rows))


if __name__ == "__main__":
    unittest.main()
