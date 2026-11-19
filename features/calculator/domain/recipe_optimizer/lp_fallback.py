"""Запасной вариант: цель недостижима — показать наименьшее нарушение.

Порядок приоритетов прежний и лексикографический: сначала минимальное
максимальное относительное нарушение, затем минимальная сумма нарушений, затем
цель режима. В отличие от прежнего численного поиска каждый шаг — задача ЛП:
при фиксированном допустимом нарушении v все ограничения линейны, поэтому
минимальное v находится бисекцией по допустимости, а сумма нарушений
минимизируется одномерным поиском по t (через него выражаются U и G).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..formulas.linear import LinearForms
from ..lp_model import (
    LpModelInfeasible,
    QualityTargets,
    solve_amounts,
    t_floor,
)
from ..lp_quality import QualityBounds, maximum_bc, maximum_t

# Бисекция по допустимому нарушению: шагов хватает на точность ~1e-9 от шкалы.
BISECTION_STEPS = 50
MAX_RELAXATION = 1.0e6
# Точки одномерного поиска по t для минимума суммы нарушений.
T_GRID = 12


@dataclass(frozen=True)
class Relaxed:
    """Пороги, ослабленные на относительное нарушение v."""

    kras_max: float
    t_min: float | None
    protein_min: float | None


def relax(
    forms: LinearForms,
    original: dict,
    scales: np.ndarray,
    violation: float,
    protein_min: float | None,
) -> Relaxed:
    """Ослабить пороги на v·масштаб каждого показателя."""
    bc = float(original["bc"]) - violation * float(scales[0])
    u_min = float(original["U"]) - violation * float(scales[1])
    g_max = float(original["G"]) + violation * float(scales[2])
    floor = None
    if protein_min is not None:
        floor = max(0.0, protein_min - violation * max(abs(protein_min), 1.0))
    return Relaxed(
        kras_max=100.0 - bc,
        t_min=t_floor(forms, u_min=u_min, g_max=g_max),
        protein_min=floor,
    )


def _feasible(
    forms: LinearForms,
    *,
    lower: np.ndarray,
    upper: np.ndarray,
    prices: np.ndarray,
    limits: Relaxed,
) -> np.ndarray | None:
    """Состав, удовлетворяющий ослабленным порогам, или `None`."""
    try:
        return solve_amounts(
            forms,
            lower=lower,
            upper=upper,
            prices=prices,
            targets=QualityTargets(
                kras_max=limits.kras_max,
                t_min=limits.t_min,
                protein_min=limits.protein_min,
            ),
        )
    except LpModelInfeasible:
        return None


def minimum_violation(
    forms: LinearForms,
    *,
    lower: np.ndarray,
    upper: np.ndarray,
    prices: np.ndarray,
    original: dict,
    scales: np.ndarray,
    protein_min: float | None,
) -> float | None:
    """Минимальное относительное нарушение, при котором задача допустима."""

    def allows(violation: float) -> bool:
        limits = relax(forms, original, scales, violation, protein_min)
        return (
            _feasible(forms, lower=lower, upper=upper, prices=prices, limits=limits)
            is not None
        )

    high = 1.0
    while not allows(high):
        high *= 4.0
        if high > MAX_RELAXATION:
            return None
    low = 0.0
    for _ in range(BISECTION_STEPS):
        middle = (low + high) / 2
        if allows(middle):
            high = middle
        else:
            low = middle
    return high


def candidates_for(
    forms: LinearForms,
    *,
    lower: np.ndarray,
    upper: np.ndarray,
    prices: np.ndarray,
    original: dict,
    scales: np.ndarray,
    protein_min: float | None,
    violation: float,
) -> list[np.ndarray]:
    """Составы при допустимом нарушении: по цене, по БЦ и по сетке значений t.

    Сетка по t — одномерный поиск: U и G зависят только от t, поэтому вместе с
    задачей «минимум КРАС при фиксированном t» она перебирает компромиссы между
    нарушениями показателей.
    """
    limits = relax(forms, original, scales, violation, protein_min)
    found: list[np.ndarray] = []
    cheapest = _feasible(forms, lower=lower, upper=upper, prices=prices, limits=limits)
    if cheapest is not None:
        found.append(cheapest)
    bounds = QualityBounds(
        kras_max=limits.kras_max, t_min=limits.t_min, protein_min=limits.protein_min
    )
    try:
        best_t_amounts, best_t = maximum_t(
            forms, lower=lower, upper=upper, bounds=bounds
        )
        found.append(best_t_amounts)
    except LpModelInfeasible:
        best_t = None
    try:
        found.append(maximum_bc(forms, lower=lower, upper=upper, bounds=bounds)[0])
    except LpModelInfeasible:
        pass
    if best_t is not None:
        start = limits.t_min if limits.t_min is not None else best_t / 2
        for step in range(1, T_GRID):
            level = start + (best_t - start) * step / T_GRID
            try:
                found.append(
                    maximum_bc(
                        forms,
                        lower=lower,
                        upper=upper,
                        bounds=QualityBounds(
                            kras_max=limits.kras_max,
                            t_min=level,
                            protein_min=limits.protein_min,
                        ),
                    )[0]
                )
            except LpModelInfeasible:
                continue
    return found
