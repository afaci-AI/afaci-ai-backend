"""Режим `cost`: состав минимальной стоимости как задача ЛП.

Пороги берутся из исходного расчёта (БЦ, U и G не хуже исходных) и переводятся
в линейные ограничения: БЦ ≥ БЦ₀ — это КРАС ≤ 100 − БЦ₀, а U ≥ U₀ вместе с
G ≤ G₀ — одно условие t ≥ t₀. Дополнительно массовая доля белка рецептуры не
опускается ниже исходной: показатели качества описывают качество белка, а не
его количество, и без этого условия оптимум уводит белок к нулю.
"""

from __future__ import annotations

import numpy as np

from ..candidates import CandidateItem, build_items
from ..formulas.linear import LinearForms, build_forms
from ..lp_model import LpModelInfeasible, QualityTargets, solve_amounts, t_floor


def forms_for(candidates: list[CandidateItem], reference: dict) -> LinearForms:
    """Линейные формы по кандидатам (от масс коэффициенты не зависят)."""
    return build_forms(build_items(candidates, np.zeros(len(candidates))), reference)


def protein_floor(forms: LinearForms, baseline: np.ndarray) -> float:
    """Массовая доля белка исходной рецептуры, г / 100 г."""
    return float(forms.protein_macro @ np.asarray(baseline, dtype=float)) / 100.0


def solve_cost(
    forms: LinearForms,
    *,
    lower: np.ndarray,
    upper: np.ndarray,
    prices: np.ndarray,
    original: dict,
    baseline: np.ndarray,
) -> np.ndarray | None:
    """Состав минимальной стоимости не хуже исходного по качеству белка.

    `None`, если задача недопустима: до этапа 5 в этом случае работает прежний
    численный запасной вариант.
    """
    targets = QualityTargets(
        kras_max=100.0 - float(original["bc"]),
        t_min=t_floor(forms, u_min=original["U"], g_max=original["G"]),
        protein_min=protein_floor(forms, baseline),
    )
    try:
        return solve_amounts(
            forms, lower=lower, upper=upper, prices=prices, targets=targets
        )
    except LpModelInfeasible:
        return None
