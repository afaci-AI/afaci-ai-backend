"""Правила домена продуктов: разница снимков и единица значения нутриента."""

import unittest
from uuid import uuid4

from features.products.domain import (
    UNIT_MISMATCH,
    UnitRuleViolation,
    changed_fields,
    nutrient_unit_for,
)


class ChangedFields(unittest.TestCase):
    def test_reports_only_differing_fields(self):
        old, new = changed_fields({"a": 1, "b": 2}, {"a": 1, "b": 3})
        self.assertEqual((old, new), ({"b": 2}, {"b": 3}))

    def test_uuid_equals_its_string(self):
        value = uuid4()
        self.assertEqual(changed_fields({"id": value}, {"id": str(value)}), ({}, {}))

    def test_field_missing_on_one_side_is_a_change(self):
        old, new = changed_fields({}, {"name": "x"})
        self.assertEqual((old, new), ({"name": None}, {"name": "x"}))


class NutrientUnit(unittest.TestCase):
    def test_name_unit_wins_and_mismatch_is_rejected(self):
        unit = uuid4()
        self.assertEqual(nutrient_unit_for(unit, None), unit)
        with self.assertRaises(UnitRuleViolation) as caught:
            nutrient_unit_for(unit, uuid4())
        self.assertEqual(caught.exception.detail, UNIT_MISMATCH)

    def test_name_without_unit_requires_requested(self):
        with self.assertRaises(UnitRuleViolation):
            nutrient_unit_for(None, None)
        unit = uuid4()
        self.assertEqual(nutrient_unit_for(None, unit), unit)


if __name__ == "__main__":
    unittest.main()
