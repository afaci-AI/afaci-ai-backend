"""Правило методики: сумма масс ингредиентов — ровно 100 г (± допуск)."""

import unittest

from features.calculator.domain import (
    EmptyRecipeError,
    InvalidRecipeSumError,
    validate_recipe_sum,
)


class RecipeSumRule(unittest.TestCase):
    def test_exactly_100_within_tolerance_passes(self):
        validate_recipe_sum([60.0, 40.0])
        validate_recipe_sum([33.333, 33.333, 33.334])
        validate_recipe_sum([50.0, 50.005])

    def test_sum_out_of_tolerance_reports_actual_total(self):
        with self.assertRaises(InvalidRecipeSumError) as caught:
            validate_recipe_sum([60.0, 39.9])
        self.assertAlmostEqual(caught.exception.actual, 99.9)
        self.assertIn("сейчас 99.90 г", str(caught.exception))

    def test_empty_recipe_is_rejected(self):
        with self.assertRaises(EmptyRecipeError):
            validate_recipe_sum([])

    def test_accepts_any_iterable_once(self):
        validate_recipe_sum(amount for amount in (25.0, 75.0))


if __name__ == "__main__":
    unittest.main()
