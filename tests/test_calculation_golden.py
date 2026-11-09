"""Golden results of the calculation core on the control recipe.

They fix current behaviour so that moving code between layers cannot silently
change a result. Regenerate only for an intentional change of the method::

    UPDATE_CALCULATION_GOLDEN=1 python -m unittest tests.test_calculation_golden
"""

import json
import math
import os
import unittest
from pathlib import Path

from domain.calculator.formulas import compute_report
from domain.calculator.optimizer import (
    CandidateItem,
    CostOptimizationConstraints,
    _build_items,
    optimize_cost,
)
from domain.calculator.recipe_optimizer import optimize_recipe

FIXTURES = Path(__file__).parent / "fixtures"
GOLDEN = FIXTURES / "calculation_golden.json"
TOLERANCE = 1e-6


def control():
    data = json.loads((FIXTURES / "control_recipe.json").read_text(encoding="utf-8"))
    candidates = [CandidateItem(**item) for item in data["candidates"]]
    return candidates, data["reference"], data["baseline_amounts"]


def plain(value):
    """Reduce numpy scalars and tuples to JSON types."""
    return json.loads(json.dumps(value, default=float))


def calculate() -> dict:
    candidates, reference, baseline = control()
    report = compute_report(_build_items(candidates, baseline), reference)
    cost = optimize_cost(
        candidates, reference, CostOptimizationConstraints(bc_min=None, kras_max=None)
    )
    return plain(
        {
            "compute_report": report,
            "optimize_cost": cost,
            "optimize_recipe_basic": optimize_recipe(
                candidates, reference, baseline, "basic"
            ),
            "optimize_recipe_cost": optimize_recipe(
                candidates, reference, baseline, "cost"
            ),
        }
    )


def differences(expected, actual, path="$") -> list[str]:
    if isinstance(expected, dict) and isinstance(actual, dict):
        out = []
        for key in sorted(set(expected) | set(actual)):
            if key not in expected or key not in actual:
                out.append(f"{path}.{key}: ключ есть не везде")
            else:
                out += differences(expected[key], actual[key], f"{path}.{key}")
        return out
    if isinstance(expected, list) and isinstance(actual, list):
        if len(expected) != len(actual):
            return [f"{path}: длина {len(expected)} != {len(actual)}"]
        return [
            d
            for i, (e, a) in enumerate(zip(expected, actual, strict=True))
            for d in differences(e, a, f"{path}[{i}]")
        ]
    numeric = (int, float)
    if (
        isinstance(expected, numeric)
        and isinstance(actual, numeric)
        and not isinstance(expected, bool)
        and not isinstance(actual, bool)
    ):
        if math.isclose(expected, actual, rel_tol=TOLERANCE, abs_tol=TOLERANCE):
            return []
        return [f"{path}: {expected} != {actual}"]
    return [] if expected == actual else [f"{path}: {expected!r} != {actual!r}"]


class CalculationGolden(unittest.TestCase):
    def test_results_match_golden(self):
        actual = calculate()
        if os.getenv("UPDATE_CALCULATION_GOLDEN") == "1":
            GOLDEN.write_text(
                json.dumps(actual, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        expected = json.loads(GOLDEN.read_text(encoding="utf-8"))
        diff = differences(expected, actual)
        self.assertEqual([], diff[:20], f"расчёт изменился ({len(diff)} отличий)")

    def test_golden_is_not_trivial(self):
        golden = json.loads(GOLDEN.read_text(encoding="utf-8"))
        self.assertIn("quality_precise", golden["compute_report"])
        self.assertTrue(golden["optimize_recipe_basic"]["optimal_items"])


if __name__ == "__main__":
    unittest.main()
