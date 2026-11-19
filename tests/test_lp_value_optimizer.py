"""Оптимизация по ценности и запасной вариант на линейном программировании.

Проверяется, что режим `basic` даёт БЦ не ниже прежнего численного поиска и не
ниже любого случайного допустимого состава, что при недостижимой цели запасной
вариант находит то же наименьшее нарушение, что независимый перебор, и что
`scipy` в проекте не осталось.
"""

import json
import re
import unittest
from dataclasses import replace
from pathlib import Path

import numpy as np

from features.calculator.domain import (
    CandidateItem,
    build_items,
    compute_report,
    optimize_recipe,
)
from features.calculator.domain.formulas.linear import build_forms
from features.calculator.domain.lp_model import fit_mass, t_floor
from features.calculator.domain.lp_quality import QualityBounds, maximum_bc, maximum_t
from features.calculator.domain.recipe_optimizer.result import FAILURE_MESSAGE

ROOT = Path(__file__).parent.parent
FIXTURES = Path(__file__).parent / "fixtures"
RANDOM_COMPOSITIONS = 500
SEED = 20261119
TOLERANCE = 1e-6
# БЦ, которую прежний поиск SLSQP давал на контрольной рецептуре
# (эталон `calculation_golden.json` до перехода на ЛП).
SLSQP_BASIC_BC = 79.34580354672252
# Наименьшее нарушение порогов в задаче с недостижимой целью ниже. Значения
# подтверждены независимым перебором: 6000 случайных составов и покоординатный
# спуск дают те же числа.
FALLBACK_MAX_VIOLATION = 0.40240067
FALLBACK_SUM_VIOLATION = 0.53790045


def control():
    data = json.loads((FIXTURES / "control_recipe.json").read_text(encoding="utf-8"))
    candidates = [CandidateItem(**item) for item in data["candidates"]]
    return candidates, data["reference"], data["baseline_amounts"]


def bounds(candidates):
    lower = np.array([c.min_amount_g for c in candidates], dtype=float)
    upper = np.array([c.max_amount_g for c in candidates], dtype=float)
    return lower, upper


def quality_of(candidates, reference, amounts):
    return compute_report(build_items(candidates, amounts), reference, rounded=False)[
        "quality_precise"
    ]


def random_compositions(candidates, count=RANDOM_COMPOSITIONS):
    lower, upper = bounds(candidates)
    rng = np.random.default_rng(SEED)
    for _ in range(count):
        yield fit_mass(rng.dirichlet(np.ones(len(candidates))) * 100.0, lower, upper)


def unreachable_goal(candidates):
    """Диапазоны, в которых исходные показатели недостижимы.

    Мясо ограничено сверху, хлеб — снизу, поэтому аминокислотный профиль
    рецептуры заведомо хуже исходного.
    """
    narrowed = list(candidates)
    narrowed[0] = replace(candidates[0], min_amount_g=0.0, max_amount_g=10.0)
    narrowed[2] = replace(candidates[2], min_amount_g=50.0, max_amount_g=60.0)
    return narrowed


def violations_of(candidates, reference, amounts, original):
    """Относительные нарушения порогов по БЦ, U и G."""
    quality = quality_of(candidates, reference, amounts)
    actual = np.array([quality["bc"], quality["U"], quality["G"]])
    base = np.array([original["bc"], original["U"], original["G"]])
    signs = np.array([1, 1, -1])
    scales = np.array([abs(v) if v != 0 else 1.0 for v in base])
    return np.maximum((base - actual) * signs, 0) / scales


class BasicMode(unittest.TestCase):
    def test_not_worse_than_previous_search(self):
        candidates, reference, baseline = control()
        result = optimize_recipe(candidates, reference, baseline, "basic")
        self.assertEqual(result["status"], "goal_achieved")
        self.assertGreaterEqual(
            result["report"]["quality_precise"]["bc"], SLSQP_BASIC_BC - TOLERANCE
        )

    def test_not_worse_than_random_compositions(self):
        candidates, reference, baseline = control()
        result = optimize_recipe(candidates, reference, baseline, "basic")
        best = result["report"]["quality_precise"]["bc"]
        before = quality_of(candidates, reference, baseline)
        for amounts in random_compositions(candidates):
            quality = quality_of(candidates, reference, amounts)
            if quality["bc"] is None:
                continue
            if quality["U"] < before["U"] or quality["G"] > before["G"]:
                continue
            self.assertGreaterEqual(best, quality["bc"] - TOLERANCE)

    def test_quality_not_worse_and_composition_verified(self):
        candidates, reference, baseline = control()
        lower, upper = bounds(candidates)
        result = optimize_recipe(candidates, reference, baseline, "basic")
        amounts = np.array([item["amount_g"] for item in result["optimal_items"]])
        self.assertAlmostEqual(float(amounts.sum()), 100.0, places=6)
        self.assertTrue(np.all(amounts >= lower - TOLERANCE))
        self.assertTrue(np.all(amounts <= upper + TOLERANCE))
        before = result["original_report"]["quality_precise"]
        after = result["report"]["quality_precise"]
        self.assertGreaterEqual(after["bc"], before["bc"] - TOLERANCE)
        self.assertGreaterEqual(after["U"], before["U"] - TOLERANCE)
        self.assertLessEqual(after["G"], before["G"] + TOLERANCE)

    def test_secondary_objective_when_bc_is_at_maximum(self):
        """Если БЦ улучшить нельзя, работает вторичная цель — максимум t."""
        candidates, reference, baseline = control()
        optimum = optimize_recipe(candidates, reference, baseline, "basic")
        best = [item["amount_g"] for item in optimum["optimal_items"]]
        again = optimize_recipe(candidates, reference, best, "basic")
        before = again["original_report"]["quality_precise"]
        after = again["report"]["quality_precise"]
        self.assertAlmostEqual(after["bc"], before["bc"], places=6)
        self.assertGreaterEqual(after["U"], before["U"] - TOLERANCE)
        self.assertLessEqual(after["G"], before["G"] + TOLERANCE)

    def test_t_bounds_agree_with_indicators(self):
        candidates, reference, baseline = control()
        forms = build_forms(build_items(candidates, baseline), reference)
        lower, upper = bounds(candidates)
        before = quality_of(candidates, reference, baseline)
        amounts, value = maximum_t(
            forms,
            lower=lower,
            upper=upper,
            bounds=QualityBounds(kras_max=100.0 - before["bc"]),
        )
        quality = quality_of(candidates, reference, amounts)
        reference_sum = forms.reference_sum
        self.assertAlmostEqual(reference_sum * value / 100.0, quality["U"], places=9)
        self.assertAlmostEqual(100.0 / value - reference_sum, quality["G"], places=9)

    def test_maximum_bc_objective_matches_recalculation(self):
        candidates, reference, baseline = control()
        forms = build_forms(build_items(candidates, baseline), reference)
        lower, upper = bounds(candidates)
        before = quality_of(candidates, reference, baseline)
        amounts, value = maximum_bc(
            forms,
            lower=lower,
            upper=upper,
            bounds=QualityBounds(
                kras_max=100.0 - before["bc"],
                t_min=t_floor(forms, u_min=before["U"], g_max=before["G"]),
            ),
        )
        self.assertAlmostEqual(
            value, quality_of(candidates, reference, amounts)["bc"], places=9
        )


class Fallback(unittest.TestCase):
    def test_minimal_violation_matches_independent_search(self):
        candidates, reference, baseline = control()
        narrowed = unreachable_goal(candidates)
        result = optimize_recipe(narrowed, reference, baseline, "basic")
        self.assertEqual(result["status"], "goal_not_achieved")
        self.assertEqual(result["message"], FAILURE_MESSAGE)
        amounts = [item["amount_g"] for item in result["optimal_items"]]
        found = violations_of(
            narrowed,
            reference,
            amounts,
            result["original_report"]["quality_precise"],
        )
        self.assertAlmostEqual(float(found.max()), FALLBACK_MAX_VIOLATION, places=6)
        self.assertAlmostEqual(float(found.sum()), FALLBACK_SUM_VIOLATION, places=6)

    def test_not_better_than_any_random_composition(self):
        candidates, reference, baseline = control()
        narrowed = unreachable_goal(candidates)
        result = optimize_recipe(narrowed, reference, baseline, "basic")
        original = result["original_report"]["quality_precise"]
        best = violations_of(
            narrowed,
            reference,
            [item["amount_g"] for item in result["optimal_items"]],
            original,
        )
        for amounts in random_compositions(narrowed):
            other = violations_of(narrowed, reference, amounts, original)
            self.assertLessEqual(float(best.max()), float(other.max()) + TOLERANCE)

    def test_violations_are_reported(self):
        candidates, reference, baseline = control()
        result = optimize_recipe(
            unreachable_goal(candidates), reference, baseline, "basic"
        )
        metrics = {item["metric"] for item in result["violations"]}
        self.assertTrue(metrics)
        for item in result["violations"]:
            self.assertGreater(item["relative"], 0)

    def test_cost_mode_falls_back_too(self):
        candidates, reference, baseline = control()
        result = optimize_recipe(
            unreachable_goal(candidates), reference, baseline, "cost"
        )
        self.assertEqual(result["status"], "goal_not_achieved")
        amounts = np.array([item["amount_g"] for item in result["optimal_items"]])
        self.assertAlmostEqual(float(amounts.sum()), 100.0, places=6)


class NoScipy(unittest.TestCase):
    def test_requirements_have_no_scipy(self):
        for name in ("requirements.txt", "requirements-dev.txt"):
            text = (ROOT / name).read_text(encoding="utf-8").lower()
            self.assertNotIn("scipy", text, name)

    def test_sources_do_not_import_scipy(self):
        """Упоминание в пояснениях допустимо, импорт — нет."""
        pattern = re.compile(r"^\s*(?:import|from)\s+scipy", re.MULTILINE)
        for package in ("features", "libs", "core"):
            for path in sorted((ROOT / package).rglob("*.py")):
                self.assertIsNone(
                    pattern.search(path.read_text(encoding="utf-8")),
                    f"{path.relative_to(ROOT)}: остался импорт scipy",
                )


if __name__ == "__main__":
    unittest.main()
