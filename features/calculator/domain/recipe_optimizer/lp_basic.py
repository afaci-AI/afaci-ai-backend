"""Режим `basic`: максимум биологической ценности как задача ЛП.

Цель дробно-линейна, поэтому решается после преобразования Чарнса–Купера
(`lp_quality.py`). Если БЦ улучшить нельзя, работает вторичная цель — максимум
t при достигнутой БЦ: правило «улучшить хотя бы один показатель» сохраняется,
потому что через t выражаются U и G.
"""

from __future__ import annotations

import numpy as np

from ..formulas.linear import LinearForms
from ..lp_model import LpModelInfeasible, t_floor
from ..lp_quality import QualityBounds, maximum_bc, maximum_t


def quality_bounds(forms: LinearForms, original: dict) -> QualityBounds:
    """Пороги исходной рецептуры: БЦ ≥ БЦ₀ (то есть КРАС ≤ КРАС₀) и t ≥ t₀."""
    return QualityBounds(
        kras_max=100.0 - float(original["bc"]),
        t_min=t_floor(forms, u_min=original["U"], g_max=original["G"]),
    )


def solve_basic(
    forms: LinearForms,
    *,
    lower: np.ndarray,
    upper: np.ndarray,
    original: dict,
    tolerance: float,
) -> np.ndarray | None:
    """Состав с максимальной БЦ, иначе — с максимальным t при той же БЦ.

    `None`, если задача недопустима: тогда работает запасной вариант.
    """
    bounds = quality_bounds(forms, original)
    try:
        amounts, best_bc = maximum_bc(forms, lower=lower, upper=upper, bounds=bounds)
    except LpModelInfeasible:
        return None
    if best_bc > float(original["bc"]) + tolerance:
        return amounts
    try:
        secondary, _ = maximum_t(
            forms,
            lower=lower,
            upper=upper,
            bounds=QualityBounds(
                kras_max=100.0 - best_bc + tolerance, t_min=bounds.t_min
            ),
        )
    except LpModelInfeasible:
        return amounts
    return secondary
