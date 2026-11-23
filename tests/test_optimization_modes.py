"""Режим оптимизации добавляется реестром, без правки ядра поиска.

Проверяется, что новый режим — это только класс и запись в `MODES`: `optimizer`,
`search`, `result` и `validation` про него ничего не знают. Заодно
фиксируется, что неизвестное имя режима по-прежнему отклоняется и что
непереданный состав важнее неизвестного режима.
"""

import json
import unittest
from pathlib import Path
from unittest.mock import patch

from features.calculator.domain import CandidateItem, optimize_recipe
from features.calculator.domain.recipe_optimizer.errors import RecipeOptimizationError
from features.calculator.domain.recipe_optimizer.lp_basic import solve_basic
from features.calculator.domain.recipe_optimizer.modes import COST_FIELDS, MODES

FIXTURES = Path(__file__).parent / "fixtures"


def control():
    data = json.loads((FIXTURES / "control_recipe.json").read_text(encoding="utf-8"))
    candidates = [CandidateItem(**item) for item in data["candidates"]]
    return candidates, data["reference"], data["baseline_amounts"]


class CheapestProteinMode:
    """Режим из одного файла теста: ядро поиска о нём не знает."""

    name = "demo"

    def protein_min(self, forms, baseline):
        return None

    def solve(self, forms, *, lower, upper, prices, original, baseline, tolerance):
        return solve_basic(
            forms, lower=lower, upper=upper, original=original, tolerance=tolerance
        )

    def rank(self, entry):
        return -entry.quality["U"]

    def improvement(self, entry, *, base_cost, margins):
        return float(margins.max())

    def price(self, candidate):
        return None

    def summary(self, *, base_cost, cost):
        return dict.fromkeys(COST_FIELDS)


class ModeRegistry(unittest.TestCase):
    def test_new_mode_needs_only_a_registry_entry(self):
        candidates, reference, baseline = control()
        with patch.dict(MODES, {"demo": CheapestProteinMode()}):
            result = optimize_recipe(candidates, reference, baseline, "demo")
        self.assertEqual("demo", result["mode"])
        self.assertTrue(result["optimal_items"])
        self.assertAlmostEqual(
            100.0, sum(item["amount_g"] for item in result["optimal_items"]), places=6
        )

    def test_mode_decides_which_fields_carry_cost(self):
        candidates, reference, baseline = control()
        with patch.dict(MODES, {"demo": CheapestProteinMode()}):
            result = optimize_recipe(candidates, reference, baseline, "demo")
        for field in COST_FIELDS:
            self.assertIsNone(result[field], field)
        for item in result["optimal_items"]:
            self.assertIsNone(item["price_per_kg"])

    def test_unknown_mode_is_rejected(self):
        candidates, reference, baseline = control()
        with self.assertRaises(RecipeOptimizationError) as caught:
            optimize_recipe(candidates, reference, baseline, "demo")
        self.assertIn("режим", str(caught.exception))

    def test_missing_composition_is_reported_before_the_mode(self):
        with self.assertRaises(RecipeOptimizationError) as caught:
            optimize_recipe([], {}, [], "demo")
        self.assertIn("исходный состав", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
