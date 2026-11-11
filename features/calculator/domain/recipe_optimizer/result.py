"""Сборка результата поиска состава: сравнение показателей и нарушения."""

from __future__ import annotations

import numpy as np

from ..candidates import CandidateItem
from .errors import COMPARISON_TOLERANCE, METRICS
from .search import EvaluatedRecipe

FAILURE_MESSAGE = (
    "Цель не достигнута; показан лучший найденный вариант. "
    "Численный поиск не доказывает невозможность улучшения."
)


def comparison(original: dict, selected: EvaluatedRecipe) -> dict:
    tol = COMPARISON_TOLERANCE
    result = {}
    for metric in ("bc", "U", "kras", "G"):
        before, after = original[metric], selected.quality[metric]
        delta = after - before
        signed = -delta if metric in ("G", "kras") else delta
        result[metric] = {
            "before": before,
            "after": after,
            "delta": delta,
            "direction": "improved"
            if signed > tol
            else "worsened"
            if signed < -tol
            else "unchanged",
        }
    # Устаревший псевдоним U для выпущенных клиентов; будет удалён.
    result["V"] = result["U"]
    return result


def violations(original: dict, selected: EvaluatedRecipe, scales: np.ndarray) -> list:
    result = []
    for i, metric in enumerate(METRICS):
        amount = max(
            0.0,
            (original[metric] - selected.quality[metric])
            * (-1 if metric == "G" else 1),
        )
        if amount > COMPARISON_TOLERANCE:
            result.append(
                {
                    "metric": metric,
                    "threshold": original[metric],
                    "actual": selected.quality[metric],
                    "amount": amount,
                    "relative": amount / scales[i],
                }
            )
    return result


def build_result(
    *,
    mode: str,
    candidates: list[CandidateItem],
    baseline: np.ndarray,
    selected: EvaluatedRecipe,
    success: bool,
    original: dict,
    original_report: dict,
    report: dict,
    scales: np.ndarray,
    base_cost: float,
) -> dict:
    is_cost = mode == "cost"
    savings = base_cost - selected.cost
    return {
        "mode": mode,
        "status": "goal_achieved" if success else "goal_not_achieved",
        "message": "Цель достигнута." if success else FAILURE_MESSAGE,
        "optimal_items": [
            {
                "product_id": c.product_id,
                "amount_g": float(selected.amounts[i]),
                "price_per_kg": c.price_per_kg if is_cost else None,
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
            "u_min": original["U"],
            "v_min": original["U"],  # устаревший псевдоним u_min
            "g_max": original["G"],
        },
        "comparison": comparison(original, selected),
        "violations": violations(original, selected, scales),
        "comparison_tolerance": COMPARISON_TOLERANCE,
        "baseline_cost_per_100g": base_cost if is_cost else None,
        "total_cost_per_100g": selected.cost if is_cost else None,
        "cost_change_per_100g": -savings if is_cost else None,
        "savings_per_100g": savings if is_cost else None,
        "savings_percent": savings / base_cost * 100
        if is_cost and base_cost != 0
        else None,
    }
