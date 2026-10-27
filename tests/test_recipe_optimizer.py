"""Deterministic checks independent of the database and deployed backend."""

import math
import unittest
from dataclasses import replace
from unittest.mock import patch

from domain.calculator.formulas import NAK_GROUPS, compute_report
from domain.calculator.optimizer import CandidateItem, _build_items
from domain.calculator.recipe_optimizer import RecipeOptimizationError, optimize_recipe


def fixture():
    reference = {
        "id": "reference",
        "name": "Control",
        "values": {g: 1.0 for g, _ in NAK_GROUPS},
    }
    candidates = []
    for index in range(2):
        amino = {}
        for group_index, (_, members) in enumerate(NAK_GROUPS):
            score = 50 if (group_index == 0) == (index == 0) else 150
            for member in members:
                amino[member] = score * 2 / len(members)
        candidates.append(
            CandidateItem(
                str(index),
                str(index),
                {"Массовая доля белка": 20},
                amino,
                100 + 100 * index,
            )
        )
    return candidates, reference


class OptimizationChecks(unittest.TestCase):
    def assert_valid(self, result, candidates, reference):
        amounts = [item["amount_g"] for item in result["optimal_items"]]
        self.assertAlmostEqual(sum(amounts), 100, places=8)
        for value, item in zip(amounts, candidates, strict=True):
            self.assertGreaterEqual(value, item.min_amount_g)
            self.assertLessEqual(value, item.max_amount_g)
        recalculated = compute_report(_build_items(candidates, amounts), reference)
        self.assertEqual(
            recalculated["quality_precise"], result["report"]["quality_precise"]
        )
        return amounts

    def test_basic_improves_all_metrics_without_prices(self):
        candidates, reference = fixture()
        result = optimize_recipe(candidates, reference, [80, 20], "basic")
        self.assertEqual(result["status"], "goal_achieved")
        amounts = self.assert_valid(result, candidates, reference)
        self.assertAlmostEqual(amounts[0], 50, places=3)
        self.assertGreater(result["comparison"]["bc"]["delta"], 0)
        self.assertEqual(result["comparison"]["G"]["direction"], "improved")
        self.assertIsNone(result["savings_percent"])
        self.assertEqual(result["violations"], [])

    def test_price_decreases_with_same_quality(self):
        candidates, reference = fixture()
        candidates[1] = replace(candidates[0], product_id="1", price_per_kg=200)
        result = optimize_recipe(candidates, reference, [50, 50], "cost")
        self.assertEqual(result["status"], "goal_achieved")
        self.assert_valid(result, candidates, reference)
        self.assertAlmostEqual(result["baseline_cost_per_100g"], 15)
        self.assertAlmostEqual(result["total_cost_per_100g"], 10, places=4)
        self.assertAlmostEqual(result["savings_percent"], 100 / 3, places=3)

    def test_fallback_is_explicit_and_reports_violations(self):
        candidates, reference = fixture()
        candidates[0] = replace(candidates[0], min_amount_g=100)
        candidates[1] = replace(candidates[1], max_amount_g=0)
        result = optimize_recipe(candidates, reference, [50, 50], "basic")
        self.assertEqual(result["status"], "goal_not_achieved")
        self.assert_valid(result, candidates, reference)
        self.assertEqual({v["metric"] for v in result["violations"]}, {"bc", "V", "G"})
        self.assertTrue(all(v["amount"] > 0 for v in result["violations"]))

    def test_fixed_composition_zero_price_is_not_saving(self):
        candidates, reference = fixture()
        candidates = [
            replace(candidates[0], min_amount_g=100, max_amount_g=100, price_per_kg=0)
        ]
        result = optimize_recipe(candidates, reference, [100], "cost")
        self.assertEqual(result["status"], "goal_not_achieved")
        self.assertIsNone(result["savings_percent"])
        self.assertEqual(result["savings_per_100g"], 0)
        self.assert_valid(result, candidates, reference)

    def test_baseline_tolerance_does_not_create_false_saving(self):
        candidates, reference = fixture()
        candidates = [replace(candidates[0], min_amount_g=100, max_amount_g=100)]
        for total in (99.991, 100.009):
            result = optimize_recipe(candidates, reference, [total], "cost")
            self.assertEqual(result["status"], "goal_not_achieved")
            self.assertAlmostEqual(result["savings_per_100g"], 0, places=12)
            self.assertEqual(result["baseline_items"][0]["amount_g"], 100)

    def test_impossible_bounds_and_bad_data(self):
        candidates, reference = fixture()
        invalid = [
            replace(candidates[0], max_amount_g=40),
            replace(candidates[1], max_amount_g=40),
        ]
        with self.assertRaises(RecipeOptimizationError):
            optimize_recipe(invalid, reference, [50, 50], "basic")
        for bad_value in (None, math.nan, math.inf, -1):
            invalid = [
                replace(
                    candidates[0], amino={**candidates[0].amino, "Лизин": bad_value}
                ),
                candidates[1],
            ]
            with self.assertRaises(RecipeOptimizationError):
                optimize_recipe(invalid, reference, [50, 50], "basic")
        invalid = [replace(candidates[0], amino={"Лизин": 100}), candidates[1]]
        with self.assertRaises(RecipeOptimizationError):
            optimize_recipe(invalid, reference, [50, 50], "basic")

    def test_solver_failure_returns_only_verified_composition(self):
        candidates, reference = fixture()
        with patch(
            "domain.calculator.recipe_optimizer.minimize",
            side_effect=RuntimeError("control"),
        ):
            result = optimize_recipe(candidates, reference, [80, 20], "basic")
        self.assert_valid(result, candidates, reference)

    def test_unrounded_comparison_detects_small_improvement(self):
        candidates, reference = fixture()
        result = optimize_recipe(candidates, reference, [50.00001, 49.99999], "basic")
        self.assertEqual(
            result["original_report"]["quality"], result["report"]["quality"]
        )
        self.assertEqual(result["status"], "goal_achieved")
        self.assertGreater(
            result["comparison"]["bc"]["delta"], result["comparison_tolerance"]
        )


if __name__ == "__main__":
    unittest.main()
