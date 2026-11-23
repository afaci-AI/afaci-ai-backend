"""Поиск состава рецептуры относительно исходного. Вся математика белка — в formulas."""

from __future__ import annotations

import numpy as np

from ..candidates import CandidateItem, build_items
from ..formulas import compute_report
from .errors import METRICS, RecipeOptimizationError
from .lp_cost import forms_for
from .modes import MODES
from .result import build_result
from .search import RecipeSearch
from .validation import is_finite, validate_data, validate_request


def optimize_recipe(
    candidates: list[CandidateItem],
    reference: dict,
    baseline_amounts: list[float],
    mode: str,
) -> dict:
    lower, upper, baseline, prices = validate_request(
        candidates, baseline_amounts, mode
    )
    strategy = MODES[mode]
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
    forms = forms_for(candidates, reference)

    search = RecipeSearch(
        candidates,
        reference,
        strategy,
        forms,
        (lower, upper),
        prices,
        base_quality,
        base_cost,
        strategy.protein_min(forms, baseline),
    )
    selected = search.run(baseline)

    return build_result(
        mode=strategy,
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
