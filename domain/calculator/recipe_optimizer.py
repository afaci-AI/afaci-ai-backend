"""Bounded recipe search. All protein mathematics remains in formulas.py.

Fallback order is lexicographic: maximum relative quality violation, sum of
relative violations, then maximum BV (basic) or minimum price (cost). For a
zero baseline the relative denominator is 1 in the metric's native units.
SLSQP is a local numerical search, not a proof of global optimality.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from scipy.optimize import Bounds, minimize

from domain.calculator.formulas import NAK_GROUPS, compute_report
from domain.calculator.optimizer import CandidateItem, _build_items

COMPARISON_TOLERANCE = 1e-6
METRICS = ("bc", "V", "G")


class RecipeOptimizationError(ValueError):
    def __init__(self, detail: str, code: str = "invalid_optimization_data"):
        super().__init__(detail)
        self.code = code


@dataclass
class EvaluatedRecipe:
    amounts: np.ndarray
    quality: dict
    cost: float
    violations: np.ndarray


def _finite(value) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(value)


def _validate_data(candidates: list[CandidateItem], reference: dict) -> None:
    for group, _ in NAK_GROUPS:
        value = reference.get("values", {}).get(group)
        if not _finite(value) or value <= 0:
            raise RecipeOptimizationError(
                f"В эталонном белке отсутствует положительное значение {group}."
            )
    for item in candidates:
        # compute_report uses zero only for absent chemical keys. Preserve that
        # policy for non-contributors; a known amino profile needs known protein.
        # An explicit NULL is still invalid and never replaced by the default.
        protein = item.chem.get("Массовая доля белка", None if item.amino else 0.0)
        if not _finite(protein) or protein < 0:
            raise RecipeOptimizationError(
                f"Для «{item.name}» отсутствует корректное содержание белка."
            )
        for value in (*item.chem.values(), *item.amino.values()):
            if not _finite(value) or value < 0:
                raise RecipeOptimizationError(
                    f"Для «{item.name}» есть пропущенные или некорректные данные состава."
                )
        # Match compute_report: a wholly absent profile is excluded from the
        # amino-acid calculation and reported as a warning, not invented as zero.
        # A present but incomplete profile still cannot support a valid search.
        if protein > 0 and item.amino:
            missing = [
                m for _, members in NAK_GROUPS for m in members if m not in item.amino
            ]
            if missing:
                raise RecipeOptimizationError(
                    f"Для «{item.name}» отсутствуют данные НАК: {', '.join(missing)}."
                )


def _project(values: np.ndarray, lower: np.ndarray, upper: np.ndarray) -> np.ndarray:
    """Euclidean projection onto the bounded simplex (exact sum, no rounding)."""
    lo = float(np.min(values - upper)) - 100.0
    hi = float(np.max(values - lower)) + 100.0
    for _ in range(80):
        midpoint = (lo + hi) / 2
        if np.clip(values - midpoint, lower, upper).sum() > 100:
            lo = midpoint
        else:
            hi = midpoint
    result = np.clip(values - (lo + hi) / 2, lower, upper)
    for i in range(len(result)):
        difference = 100.0 - float(result.sum())
        result[i] += np.clip(difference, lower[i] - result[i], upper[i] - result[i])
    return result


def optimize_recipe(
    candidates: list[CandidateItem],
    reference: dict,
    baseline_amounts: list[float],
    mode: str,
) -> dict:
    tol = COMPARISON_TOLERANCE
    if not candidates or len(candidates) != len(baseline_amounts):
        raise RecipeOptimizationError("Не передан исходный состав рецептуры.")
    if mode not in ("basic", "cost"):
        raise RecipeOptimizationError("Неизвестный режим оптимизации.")
    lower = np.array([c.min_amount_g for c in candidates], dtype=float)
    upper = np.array([c.max_amount_g for c in candidates], dtype=float)
    baseline = np.asarray(baseline_amounts, dtype=float)
    prices = np.array([c.price_per_kg / 1000 for c in candidates], dtype=float)
    if (
        not all(np.isfinite(v).all() for v in (lower, upper, baseline, prices))
        or np.any(lower < 0)
        or np.any(upper > 100)
        or np.any(lower > upper)
        or np.any(baseline < 0)
        or np.any(prices < 0)
        or abs(float(baseline.sum()) - 100) > 0.01
    ):
        raise RecipeOptimizationError("Некорректные массы, цены или диапазоны.")
    if float(lower.sum()) > 100 or float(upper.sum()) < 100:
        raise RecipeOptimizationError("В заданных диапазонах нельзя составить 100 г.")
    baseline = baseline * (100.0 / float(baseline.sum()))
    _validate_data(candidates, reference)
    original_report = compute_report(_build_items(candidates, baseline), reference)
    original = original_report["quality_precise"]
    if not all(_finite(original.get(metric)) for metric in (*METRICS, "kras")):
        raise RecipeOptimizationError(
            "Невозможно рассчитать БЦ, V и G исходной рецептуры: проверьте данные НАК и белок."
        )
    base_quality = np.array([original[m] for m in METRICS])
    # No arbitrary weights: each violation is divided by its own baseline.
    scales = np.array([abs(v) if v != 0 else 1.0 for v in base_quality])
    base_cost = float(np.dot(prices, baseline))
    records: dict[tuple, EvaluatedRecipe | None] = {}

    def evaluate(x) -> EvaluatedRecipe | None:
        key = tuple(float(v) for v in x)
        if key in records:
            return records[key]
        records[key] = None
        if (
            not np.isfinite(x).all()
            or np.any(x < lower - tol)
            or np.any(x > upper + tol)
            or abs(float(np.sum(x)) - 100) > tol
        ):
            return None
        # Evaluate the exact composition that will be returned and saved.
        amounts = _project(np.asarray(x), lower, upper)
        try:
            quality = compute_report(
                _build_items(candidates, amounts), reference, rounded=False
            )["quality_precise"]
        except (ArithmeticError, TypeError, ValueError):
            return None
        if not all(_finite(quality.get(m)) for m in (*METRICS, "kras")):
            return None
        actual = np.array([quality[m] for m in METRICS])
        differences = (base_quality - actual) * np.array([1, 1, -1])
        violation = np.maximum(differences, 0) / scales
        result = EvaluatedRecipe(
            amounts, quality, float(np.dot(prices, amounts)), violation
        )
        records[key] = result
        return result

    def objective(x):
        entry = evaluate(x)
        if entry is None:
            return 1e12
        return entry.cost if mode == "cost" else -entry.quality["bc"]

    def quality_margin(x):
        entry = evaluate(x)
        if entry is None:
            return np.full(3, -1e12)
        actual = np.array([entry.quality[m] for m in METRICS])
        return (actual - base_quality) * np.array([1, 1, -1])

    equality = {"type": "eq", "fun": lambda x: float(np.sum(x)) - 100}
    bounds = Bounds(lower, upper)
    rng = np.random.default_rng(42)
    starts = [
        _project(baseline, lower, upper),
        _project(np.full(len(candidates), 100 / len(candidates)), lower, upper),
    ]
    for _ in range(5):
        starts.append(
            _project(rng.dirichlet(np.ones(len(candidates))) * 100, lower, upper)
        )
    if mode == "cost":
        cheapest = lower.copy()
        for index in np.argsort(prices):
            cheapest[index] += min(upper[index] - cheapest[index], 100 - cheapest.sum())
        starts.append(cheapest)

    def search(fun, start, extra):
        evaluate(start)
        try:
            result = minimize(
                fun,
                start,
                method="SLSQP",
                bounds=bounds,
                constraints=[equality, *extra],
                options={"ftol": 1e-10, "maxiter": 250, "disp": False},
            )
            evaluate(result.x)
        except (ArithmeticError, ValueError, RuntimeError):
            pass

    for start in starts:
        search(objective, start, [{"type": "ineq", "fun": quality_margin}])

    def entries():
        return [entry for entry in records.values() if entry is not None]

    def achieved(entry):
        margins = (
            np.array([entry.quality[m] for m in METRICS]) - base_quality
        ) * np.array([1, 1, -1])
        improvement = base_cost - entry.cost if mode == "cost" else float(margins.max())
        return bool(np.all(margins >= -tol) and improvement > tol)

    found = [entry for entry in entries() if achieved(entry)]
    if not found:
        # Lexicographic fallback, without mixing metric priorities into weights.
        def maximum(x):
            entry = evaluate(x)
            return float(entry.violations.max()) if entry else 1e12

        def total(x):
            entry = evaluate(x)
            return float(entry.violations.sum()) if entry else 1e12

        for start in starts:
            search(maximum, start, [])
        if entries():
            best_max = min(float(e.violations.max()) for e in entries())
            max_constraint = {
                "type": "ineq",
                "fun": lambda x: best_max + tol - maximum(x),
            }
            stage_starts = sorted(entries(), key=lambda e: e.violations.max())[:3]
            for entry in stage_starts:
                search(total, entry.amounts, [max_constraint])
            permitted = [e for e in entries() if e.violations.max() <= best_max + tol]
            best_sum = min(float(e.violations.sum()) for e in permitted)
            total_constraint = {
                "type": "ineq",
                "fun": lambda x: best_sum + tol - total(x),
            }
            for entry in sorted(permitted, key=lambda e: e.violations.sum())[:3]:
                search(objective, entry.amounts, [max_constraint, total_constraint])
        found = [entry for entry in entries() if achieved(entry)]

    if found:
        selected = min(
            found, key=lambda e: e.cost if mode == "cost" else -e.quality["bc"]
        )
    else:
        available = entries()
        if not available:
            raise RecipeOptimizationError(
                "Не удалось получить и проверить рассчитываемый состав в заданных диапазонах.",
                "optimization_calculation_failed",
            )
        best_max = min(float(e.violations.max()) for e in available)
        available = [e for e in available if e.violations.max() <= best_max + tol]
        best_sum = min(float(e.violations.sum()) for e in available)
        available = [e for e in available if e.violations.sum() <= best_sum + tol]
        selected = min(
            available, key=lambda e: e.cost if mode == "cost" else -e.quality["bc"]
        )

    report = compute_report(_build_items(candidates, selected.amounts), reference)
    comparison = {}
    for metric in ("bc", "V", "kras", "G"):
        before, after = original[metric], selected.quality[metric]
        delta = after - before
        signed = -delta if metric in ("G", "kras") else delta
        comparison[metric] = {
            "before": before,
            "after": after,
            "delta": delta,
            "direction": "improved"
            if signed > tol
            else "worsened"
            if signed < -tol
            else "unchanged",
        }
    violations = []
    for i, metric in enumerate(METRICS):
        amount = max(
            0.0,
            (original[metric] - selected.quality[metric])
            * (-1 if metric == "G" else 1),
        )
        if amount > tol:
            violations.append(
                {
                    "metric": metric,
                    "threshold": original[metric],
                    "actual": selected.quality[metric],
                    "amount": amount,
                    "relative": amount / scales[i],
                }
            )
    success = achieved(selected)
    savings = base_cost - selected.cost
    return {
        "mode": mode,
        "status": "goal_achieved" if success else "goal_not_achieved",
        "message": "Цель достигнута."
        if success
        else "Цель не достигнута; показан лучший найденный вариант. Численный поиск не доказывает невозможность улучшения.",
        "optimal_items": [
            {
                "product_id": c.product_id,
                "amount_g": float(selected.amounts[i]),
                "price_per_kg": c.price_per_kg if mode == "cost" else None,
            }
            for i, c in enumerate(candidates)
        ],
        "baseline_items": [
            {"product_id": c.product_id, "amount_g": float(baseline[i])}
            for i, c in enumerate(candidates)
        ],
        "original_report": original_report,
        "report": report,
        "thresholds": {
            "bc_min": original["bc"],
            "v_min": original["V"],
            "g_max": original["G"],
        },
        "comparison": comparison,
        "violations": violations,
        "comparison_tolerance": tol,
        "baseline_cost_per_100g": base_cost if mode == "cost" else None,
        "total_cost_per_100g": selected.cost if mode == "cost" else None,
        "cost_change_per_100g": -savings if mode == "cost" else None,
        "savings_per_100g": savings if mode == "cost" else None,
        "savings_percent": savings / base_cost * 100
        if mode == "cost" and base_cost != 0
        else None,
    }
