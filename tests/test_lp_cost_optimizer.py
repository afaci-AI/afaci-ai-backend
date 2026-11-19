"""Оптимизация по цене на линейном программировании.

Проверяется три вещи: линейные формы совпадают с методикой, найденная цена не
выше цены прежнего численного поиска и любого случайного допустимого состава,
а новое ограничение по белку (решение 4 этапа 3) соблюдается.
"""

import json
import unittest
from pathlib import Path

import numpy as np

from features.calculator.domain import (
    CandidateItem,
    CostOptimizationConstraints,
    OptimizationInfeasibleError,
    build_items,
    compute_report,
    optimize_cost,
    optimize_recipe,
)
from features.calculator.domain.cost_optimizer import kras_limit
from features.calculator.domain.formulas import NAK_GROUPS
from features.calculator.domain.formulas.linear import indicators
from features.calculator.domain.lp_model import QualityTargets, solve_amounts, t_floor
from features.calculator.domain.recipe_optimizer.lp_cost import forms_for
from features.calculator.domain.recipe_optimizer.simplex import project

FIXTURES = Path(__file__).parent / "fixtures"
RANDOM_COMPOSITIONS = 500
SEED = 20261119
# Результаты прежнего поиска SLSQP на контрольной рецептуре (эталон
# `calculation_golden.json` до перехода на ЛП): цена не должна стать выше.
SLSQP_COST_UNCONSTRAINED = 17.198999999999995
SLSQP_COST_RECIPE_MODE = 17.832874999254916
TOLERANCE = 1e-6


def control():
    data = json.loads((FIXTURES / "control_recipe.json").read_text(encoding="utf-8"))
    candidates = [CandidateItem(**item) for item in data["candidates"]]
    return candidates, data["reference"], data["baseline_amounts"]


def bounds(candidates):
    lower = np.array([c.min_amount_g for c in candidates], dtype=float)
    upper = np.array([c.max_amount_g for c in candidates], dtype=float)
    prices = np.array([c.price_per_kg / 1000.0 for c in candidates], dtype=float)
    return lower, upper, prices


def random_compositions(candidates, count=RANDOM_COMPOSITIONS):
    """Случайные составы в границах с суммой 100 г."""
    lower, upper, _ = bounds(candidates)
    rng = np.random.default_rng(SEED)
    for _ in range(count):
        yield project(rng.dirichlet(np.ones(len(candidates))) * 100.0, lower, upper)


def quality_of(candidates, reference, amounts):
    report = compute_report(build_items(candidates, amounts), reference, rounded=False)
    return report["quality_precise"], report["macro"]["protein"]


def simple_reference():
    values = [4.0, 7.0, 5.0, 3.5, 6.0, 1.0, 4.0, 5.5]
    return {
        "id": "reference",
        "name": "ФАО/ВОЗ 1973",
        "values": {
            group: value for (group, _), value in zip(NAK_GROUPS, values, strict=True)
        },
    }


def meat_and_water():
    """Пример решения 4: показатели качества не зависят от количества белка."""
    amino = {
        "Изолейцин": 530.44,
        "Лейцин": 1121.4,
        "Валин": 632.86,
        "Метионин": 315.0,
        "Цистеин": 180.0,
        "Фенилаланин": 560.0,
        "Тирозин": 480.0,
        "Триптофан": 160.0,
        "Треонин": 590.0,
        "Лизин": 1180.0,
    }
    meat = CandidateItem(
        "1",
        "Говядина котлетная",
        {"Массовая доля белка": 17.8, "Массовая доля жира": 10.0, "Углеводы": 0.6},
        amino,
        100.0,
        0.0,
        100.0,
    )
    water = CandidateItem(
        "2",
        "Вода",
        {"Массовая доля белка": 0.0, "Массовая доля жира": 0.0, "Углеводы": 0.0},
        {},
        0.0,
        0.0,
        100.0,
    )
    return [meat, water]


class LinearForms(unittest.TestCase):
    def test_match_compute_report(self):
        candidates, reference, _ = control()
        forms = forms_for(candidates, reference)
        worst = 0.0
        for amounts in random_compositions(candidates, 200):
            precise, _ = quality_of(candidates, reference, amounts)
            linear = indicators(forms, amounts)
            self.assertIsNotNone(linear)
            for metric in ("kras", "bc", "U", "G"):
                worst = max(worst, abs(precise[metric] - linear[metric]))
        self.assertLess(worst, 1e-10, f"линейные формы расходятся с методикой: {worst}")

    def test_t_floor_reproduces_u_and_g(self):
        candidates, reference, baseline = control()
        forms = forms_for(candidates, reference)
        precise, _ = quality_of(candidates, reference, baseline)
        floor = t_floor(forms, u_min=precise["U"], g_max=precise["G"])
        reference_sum = forms.reference_sum
        self.assertAlmostEqual(reference_sum * floor / 100.0, precise["U"], places=9)
        self.assertAlmostEqual(100.0 / floor - reference_sum, precise["G"], places=9)

    def test_kras_limit_takes_the_strictest(self):
        self.assertIsNone(kras_limit(CostOptimizationConstraints()))
        self.assertEqual(kras_limit(CostOptimizationConstraints(bc_min=80.0)), 20.0)
        self.assertEqual(
            kras_limit(CostOptimizationConstraints(bc_min=80.0, kras_max=15.0)), 15.0
        )
        self.assertEqual(
            kras_limit(CostOptimizationConstraints(bc_min=90.0, kras_max=15.0)), 10.0
        )


class CostOptimization(unittest.TestCase):
    def test_not_worse_than_previous_search(self):
        candidates, reference, _ = control()
        result = optimize_cost(candidates, reference, CostOptimizationConstraints())
        self.assertLessEqual(
            result["total_cost_per_100g"], SLSQP_COST_UNCONSTRAINED + TOLERANCE
        )

    def test_not_worse_than_random_compositions(self):
        candidates, reference, _ = control()
        _, _, prices = bounds(candidates)
        limit = 21.5
        result = optimize_cost(
            candidates, reference, CostOptimizationConstraints(kras_max=limit)
        )
        precise, _ = quality_of(candidates, reference, result["amounts"])
        self.assertLessEqual(precise["kras"], limit + TOLERANCE)
        for amounts in random_compositions(candidates):
            quality, _ = quality_of(candidates, reference, amounts)
            if quality["kras"] is None or quality["kras"] > limit:
                continue
            self.assertLessEqual(
                result["total_cost_per_100g"],
                float(prices @ amounts) + TOLERANCE,
                "ЛП дороже случайного допустимого состава",
            )

    def test_sum_and_bounds_hold(self):
        candidates, reference, _ = control()
        lower, upper, _ = bounds(candidates)
        amounts = np.array(
            optimize_cost(candidates, reference, CostOptimizationConstraints())[
                "amounts"
            ]
        )
        self.assertAlmostEqual(float(amounts.sum()), 100.0, places=8)
        self.assertTrue(np.all(amounts >= lower - TOLERANCE))
        self.assertTrue(np.all(amounts <= upper + TOLERANCE))

    def test_feasibility_boundary_matches_search(self):
        """Минимальный достижимый КРАС на контрольной рецептуре — 20.6542.

        Значение найдено независимым поиском (случайные составы и покоординатный
        спуск); ЛП объявляет задачу недопустимой ровно ниже него.
        """
        candidates, reference, _ = control()
        minimum = 20.6542
        result = optimize_cost(
            candidates, reference, CostOptimizationConstraints(kras_max=minimum + 0.01)
        )
        precise, _ = quality_of(candidates, reference, result["amounts"])
        self.assertLessEqual(precise["kras"], minimum + 0.01 + TOLERANCE)
        with self.assertRaises(OptimizationInfeasibleError):
            optimize_cost(
                candidates,
                reference,
                CostOptimizationConstraints(kras_max=minimum - 0.01),
            )

    def test_impossible_quality_is_infeasible(self):
        candidates, reference, _ = control()
        with self.assertRaises(OptimizationInfeasibleError):
            optimize_cost(
                candidates, reference, CostOptimizationConstraints(bc_min=99.9)
            )

    def test_bounds_without_hundred_grams(self):
        candidates, reference, _ = control()
        narrow = [CandidateItem(**{**vars(c), "max_amount_g": 1.0}) for c in candidates]
        with self.assertRaises(OptimizationInfeasibleError):
            optimize_cost(narrow, reference, CostOptimizationConstraints())


class RecipeCostMode(unittest.TestCase):
    def test_not_worse_than_previous_search(self):
        candidates, reference, baseline = control()
        result = optimize_recipe(candidates, reference, baseline, "cost")
        self.assertEqual(result["status"], "goal_achieved")
        self.assertLessEqual(
            result["total_cost_per_100g"], SLSQP_COST_RECIPE_MODE + TOLERANCE
        )
        self.assertEqual(result["violations"], [])

    def test_quality_and_protein_not_worse(self):
        candidates, reference, baseline = control()
        result = optimize_recipe(candidates, reference, baseline, "cost")
        before = result["original_report"]["quality_precise"]
        after = result["report"]["quality_precise"]
        self.assertGreaterEqual(after["bc"], before["bc"] - TOLERANCE)
        self.assertGreaterEqual(after["U"], before["U"] - TOLERANCE)
        self.assertLessEqual(after["G"], before["G"] + TOLERANCE)
        self.assertGreaterEqual(
            result["report"]["macro"]["protein"],
            result["original_report"]["macro"]["protein"] - TOLERANCE,
        )

    def test_not_worse_than_random_compositions(self):
        candidates, reference, baseline = control()
        _, _, prices = bounds(candidates)
        result = optimize_recipe(candidates, reference, baseline, "cost")
        before, protein_before = quality_of(candidates, reference, baseline)
        for amounts in random_compositions(candidates):
            quality, protein = quality_of(candidates, reference, amounts)
            if quality["bc"] is None:
                continue
            feasible = (
                quality["bc"] >= before["bc"]
                and quality["U"] >= before["U"]
                and quality["G"] <= before["G"]
                and protein >= protein_before
            )
            if not feasible:
                continue
            self.assertLessEqual(
                result["total_cost_per_100g"], float(prices @ amounts) + TOLERANCE
            )

    def test_protein_floor_keeps_meat(self):
        """Решение 4: белок не ниже исходного, поэтому мясо остаётся 60 г."""
        candidates = meat_and_water()
        result = optimize_recipe(candidates, simple_reference(), [60.0, 40.0], "cost")
        amounts = [item["amount_g"] for item in result["optimal_items"]]
        self.assertGreaterEqual(amounts[0], 60.0 - 1e-4)
        self.assertGreaterEqual(
            result["report"]["macro"]["protein"],
            result["original_report"]["macro"]["protein"] - TOLERANCE,
        )

    def test_basic_mode_untouched(self):
        candidates, reference, baseline = control()
        result = optimize_recipe(candidates, reference, baseline, "basic")
        self.assertEqual(result["mode"], "basic")
        self.assertIsNone(result["total_cost_per_100g"])


class ModelStructure(unittest.TestCase):
    def test_infeasible_targets_raise(self):
        candidates, reference, _ = control()
        forms = forms_for(candidates, reference)
        lower, upper, prices = bounds(candidates)
        from features.calculator.domain.lp_model import LpModelInfeasible

        with self.assertRaises(LpModelInfeasible):
            solve_amounts(
                forms,
                lower=lower,
                upper=upper,
                prices=prices,
                targets=QualityTargets(kras_max=0.0, t_min=10.0),
            )

    def test_no_third_party_solvers(self):
        """В оптимизаторах нет сторонних решателей ЛП (только свой `libs.lp`)."""
        root = Path(__file__).parent.parent / "features" / "calculator" / "domain"
        for path in (
            root / "cost_optimizer.py",
            root / "lp_model.py",
            root / "formulas" / "linear.py",
            root / "recipe_optimizer" / "lp_cost.py",
        ):
            text = path.read_text(encoding="utf-8")
            for forbidden in ("linprog", "highs", "pulp", "ortools", "cvxpy", "scipy"):
                self.assertNotIn(forbidden, text.lower(), f"{path.name}: {forbidden}")


if __name__ == "__main__":
    unittest.main()
