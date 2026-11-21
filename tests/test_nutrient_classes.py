"""Классы нутриентов: правила по умолчанию, микросостав рецептуры, строки без нормы."""

import unittest

from features.calculator.domain.formulas.composition import composition_rows
from features.calculator.domain.formulas.data_warnings import composition_warning
from features.catalog.domain.nutrient_classes import (
    MACRO_NAMES,
    NUTRIENT_CLASSES,
    default_nutrient_class,
)
from features.norms.domain.daily_norms import build_class_rows, short_unit


def item(amount, micro=None, other=None):
    return {
        "amount_g": amount,
        "micro": micro or {},
        "other": other or {},
        "units": {name: "мг/100г" for name in (micro or {})}
        | {name: "%/100г" for name in (other or {})},
    }


class DefaultClass(unittest.TestCase):
    def test_class_follows_nutrient_type(self):
        self.assertEqual(default_nutrient_class("Минеральный состав"), "micro")
        self.assertEqual(default_nutrient_class("Аминокислотный состав"), "amino")
        self.assertEqual(default_nutrient_class("Химический состав"), "other")

    def test_unknown_type_is_other(self):
        self.assertEqual(default_nutrient_class("Витамины"), "other")
        self.assertEqual(default_nutrient_class(None), "other")

    def test_every_default_is_a_known_class(self):
        for type_name in ("Минеральный состав", "Аминокислотный состав", "Прочее"):
            self.assertIn(default_nutrient_class(type_name), NUTRIENT_CLASSES)

    def test_macro_names_are_not_defaulted_to_macro(self):
        # БЖУ и волокна переводит в macro миграция; по типу они «прочее».
        self.assertEqual(len(MACRO_NAMES), 4)
        self.assertEqual(default_nutrient_class("Химический состав"), "other")


class RecipeComposition(unittest.TestCase):
    def test_sum_is_weighted_by_amount(self):
        rows = composition_rows(
            [item(60, {"Ca": 100.0}), item(40, {"Ca": 50.0})], "micro"
        )
        self.assertEqual(len(rows), 1)
        self.assertAlmostEqual(rows[0]["amount"], 80.0)
        self.assertFalse(rows[0]["partial"])
        self.assertEqual(rows[0]["unit"], "мг/100г")

    def test_mineral_known_to_nobody_is_absent(self):
        rows = composition_rows([item(100, {"Ca": 10.0})], "micro")
        self.assertEqual([row["name"] for row in rows], ["Ca"])

    def test_mineral_known_to_part_is_partial(self):
        rows = composition_rows([item(70, {"Fe": 2.0}), item(30)], "micro")
        self.assertAlmostEqual(rows[0]["amount"], 1.4)
        self.assertTrue(rows[0]["partial"])

    def test_zero_mass_ingredient_does_not_make_value_partial(self):
        rows = composition_rows([item(100, {"Fe": 2.0}), item(0)], "micro")
        self.assertFalse(rows[0]["partial"])

    def test_other_class_is_separate_field(self):
        items = [item(100, {"Ca": 1.0}, {"Массовая доля влаги": 70.0})]
        self.assertEqual(
            [row["name"] for row in composition_rows(items, "other")],
            ["Массовая доля влаги"],
        )

    def test_items_without_class_fields_give_no_rows(self):
        self.assertEqual(composition_rows([{"amount_g": 100}], "micro"), [])

    def test_warning_only_for_partial_rows(self):
        full = [{"name": "Ca", "partial": False}]
        part = [{"name": "Fe", "partial": True}]
        self.assertEqual(composition_warning(full), [])
        self.assertIn("Fe", composition_warning(part)[0])


class ClassRows(unittest.TestCase):
    def test_rows_have_no_norm_and_short_unit(self):
        rows = build_class_rows([{"name": "Ca", "unit": "мг/100г", "amount": 12.0}])
        self.assertEqual(rows[0]["unit"], "мг")
        self.assertIsNone(rows[0]["norm"])
        self.assertIsNone(rows[0]["percent"])
        self.assertFalse(rows[0]["partial"])

    def test_partial_flag_is_kept(self):
        rows = build_class_rows(
            [{"name": "Fe", "unit": None, "amount": 1.0, "partial": True}]
        )
        self.assertTrue(rows[0]["partial"])
        self.assertIsNone(rows[0]["unit"])

    def test_short_unit(self):
        self.assertEqual(short_unit("%/100г"), "%")
        self.assertIsNone(short_unit(None))


if __name__ == "__main__":
    unittest.main()
