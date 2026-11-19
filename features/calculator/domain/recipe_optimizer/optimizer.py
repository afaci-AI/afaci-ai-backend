"""Поиск состава рецептуры относительно исходного. Вся математика белка — в formulas."""

from __future__ import annotations

import numpy as np

from ..candidates import CandidateItem, build_items
from ..formulas import compute_report
from .errors import COMPARISON_TOLERANCE, METRICS, RecipeOptimizationError
from .lp_cost import forms_for, solve_cost
from .result import build_result
from .search import EvaluatedRecipe, RecipeSearch
from .simplex import build_starts
from .validation import is_finite, validate_data, validate_request


def _lp_cost_entry(
    search: RecipeSearch,
    candidates: list[CandidateItem],
    reference: dict,
    baseline: np.ndarray,
    mode: str,
) -> EvaluatedRecipe | None:
    """Состав режима `cost` из ЛП, уже пересчитанный методикой.

    `None` — задача ЛП недопустима или состав не прошёл пересчёт; тогда
    работает прежний численный поиск (до этапа 5 он остаётся запасным).
    """
    if mode != "cost":
        return None
    amounts = solve_cost(
        forms_for(candidates, reference),
        lower=search.lower,
        upper=search.upper,
        prices=search.prices,
        original={
            metric: value
            for metric, value in zip(METRICS, search.base_quality, strict=True)
        },
        baseline=baseline,
    )
    if amounts is None:
        return None
    entry = search.evaluate(amounts)
    if entry is None or np.any(search.margins(entry) < -COMPARISON_TOLERANCE):
        return None
    return entry


def optimize_recipe(
    candidates: list[CandidateItem],
    reference: dict,
    baseline_amounts: list[float],
    mode: str,
) -> dict:
    lower, upper, baseline, prices = validate_request(
        candidates, baseline_amounts, mode
    )
    baseline = baseline * (100.0 / float(baseline.sum()))
    validate_data(candidates, reference)
    original_report = compute_report(build_items(candidates, baseline), reference)
    original = original_report["quality_precise"]
    if not all(is_finite(original.get(metric)) for metric in (*METRICS, "kras")):
        raise RecipeOptimizationError(
            "Невозможно рассчитать БЦ, U и G исходной рецептуры: проверьте данные НАК и белок."
        )
    base_quality = np.array([original[m] for m in METRICS])
    base_cost = float(np.dot(prices, baseline))

    search = RecipeSearch(
        candidates, reference, mode, (lower, upper), prices, base_quality, base_cost
    )
    selected = _lp_cost_entry(search, candidates, reference, baseline, mode)
    if selected is None:
        selected = search.run(build_starts(baseline, lower, upper, prices, mode))

    return build_result(
        mode=mode,
        candidates=candidates,
        baseline=baseline,
        selected=selected,
        success=search.achieved(selected),
        original=original,
        original_report=original_report,
        report=compute_report(build_items(candidates, selected.amounts), reference),
        scales=search.scales,
        base_cost=base_cost,
    )
