"""Utility coefficient is denoted U; V stays only as a deprecated API alias."""

import json
import unittest
from pathlib import Path

from core.db.models import SavedRecipe
from features.calculator.domain import CandidateItem
from features.calculator.domain import build_items as _build_items
from features.calculator.domain.formulas import compute_report
from features.calculator.domain.recipe_optimizer import optimize_recipe
from features.recipes.api.schemas import Weights
from features.recipes.domain import metrics_from_report
from features.recipes.infra.mapper import apply_metrics


def control():
    data = json.loads(
        (Path(__file__).parent / "fixtures" / "control_recipe.json").read_text()
    )
    candidates = [CandidateItem(**item) for item in data["candidates"]]
    return candidates, data["reference"], data["baseline_amounts"]


class UtilityCoefficientChecks(unittest.TestCase):
    def test_report_has_u_and_deprecated_v_alias(self):
        candidates, reference, amounts = control()
        report = compute_report(_build_items(candidates, amounts), reference)
        self.assertEqual(report["quality"]["U"], 0.79)
        self.assertEqual(report["quality"]["V"], report["quality"]["U"])
        precise = report["quality_precise"]
        self.assertAlmostEqual(precise["U"], 0.78524439, places=7)
        self.assertEqual(precise["V"], precise["U"])

    def test_optimizer_uses_u_with_v_aliases(self):
        candidates, reference, amounts = control()
        result = optimize_recipe(candidates, reference, amounts, "basic")
        self.assertEqual(result["thresholds"]["u_min"], result["thresholds"]["v_min"])
        self.assertIn("U", result["comparison"])
        self.assertIs(result["comparison"]["V"], result["comparison"]["U"])
        for violation in result["violations"]:
            self.assertIn(violation["metric"], {"bc", "U", "G"})

    def test_ranking_weights_accept_u_and_legacy_v(self):
        self.assertEqual(Weights().utility, 0.25)
        self.assertEqual(Weights(v=0.4).utility, 0.4)
        self.assertEqual(Weights(u=0.1, v=0.4).utility, 0.1)

    def test_saved_recipe_metrics_use_u_column(self):
        recipe = SavedRecipe()
        apply_metrics(
            recipe,
            metrics_from_report(
                {"quality": {"bc": 1, "kras": 2, "U": 0.5, "G": 3}, "c_min": {}}
            ),
        )
        self.assertEqual(recipe.u_coef, 0.5)
        self.assertFalse(hasattr(recipe, "v_coef"))


if __name__ == "__main__":
    unittest.main()
