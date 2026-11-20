"""Оптимизация стоимости рецептуры: одна задача линейного программирования.

Чистая вычислительная логика без обращения к БД. Задача: найти долевой состав
(Xᵢ, г / 100 г) минимальной стоимости при ограничениях на качество белка
(БЦ, КРАС). Показатели методики нелинейны, но сводятся к линейным формам
(`formulas/linear.py`), поэтому состав находится двойственным симплекс-методом
из `libs.lp`: он либо даёт оптимум, либо доказывает недостижимость порогов.
"""

from __future__ import annotations

import numpy as np

from .candidates import CandidateItem, CostOptimizationConstraints, build_items
from .exceptions import OptimizationInfeasibleError
from .formulas import compute_report
from .formulas.linear import build_forms
from .lp_model import LpModelInfeasible, QualityTargets, solve_amounts

# Допуск проверки итогового состава: пороги не должны нарушаться больше него.
CHECK_TOLERANCE = 1.0e-6


def _check_bounds(lower: np.ndarray, upper: np.ndarray) -> None:
    """Ранняя проверка допустимости по границам."""
    if lower.sum() > 100.0 + 1e-6:
        raise OptimizationInfeasibleError(
            f"Сумма нижних границ Xᵢ ({lower.sum():.2f} г) превышает 100 г."
        )
    if upper.sum() < 100.0 - 1e-6:
        raise OptimizationInfeasibleError(
            f"Сумма верхних границ Xᵢ ({upper.sum():.2f} г) меньше 100 г."
        )


def kras_limit(constraints: CostOptimizationConstraints) -> float | None:
    """Единый предел КРАС: БЦ ≥ bc_min равносильно КРАС ≤ 100 − bc_min."""
    limits: list[float] = []
    if constraints.bc_min is not None:
        limits.append(100.0 - float(constraints.bc_min))
    if constraints.kras_max is not None:
        limits.append(float(constraints.kras_max))
    return min(limits) if limits else None


def _verify(
    candidates: list[CandidateItem],
    reference: dict,
    amounts: np.ndarray,
    limit: float | None,
) -> None:
    """Пересчёт итогового состава методикой: непроверенные составы не отдаём."""
    if limit is None:
        return
    report = compute_report(build_items(candidates, amounts), reference, rounded=False)
    kras = report["quality_precise"]["kras"]
    if kras is None or kras > limit + CHECK_TOLERANCE:
        raise OptimizationInfeasibleError(
            "Найденный состав не прошёл проверку методикой: "
            f"КРАС {kras} при пределе {limit}."
        )


def optimize_cost(
    candidates: list[CandidateItem],
    reference: dict,
    constraints: CostOptimizationConstraints,
) -> dict:
    """Находит состав рецептуры с минимальной стоимостью.

    Возвращает {"amounts": list[float], "total_cost_per_100g": float}.
    Бросает OptimizationInfeasibleError, если задача неразрешима.
    """
    if not candidates:
        raise OptimizationInfeasibleError("Список кандидатов пуст.")

    lower = np.array([c.min_amount_g for c in candidates], dtype=float)
    upper = np.array([c.max_amount_g for c in candidates], dtype=float)
    _check_bounds(lower, upper)
    prices = np.array(
        [c.price_per_kg / 1000.0 for c in candidates]
    )  # внутренняя единица: стоимость грамма

    forms = build_forms(build_items(candidates, np.zeros(len(candidates))), reference)
    limit = kras_limit(constraints)
    try:
        amounts = solve_amounts(
            forms,
            lower=lower,
            upper=upper,
            prices=prices,
            targets=QualityTargets(kras_max=limit),
        )
    except LpModelInfeasible as error:
        raise OptimizationInfeasibleError(
            "В заданных диапазонах Xᵢ нет состава, удовлетворяющего ограничениям "
            "по качеству белка. Ослабьте ограничения или расширьте диапазоны."
        ) from error

    _verify(candidates, reference, amounts, limit)
    return {
        "amounts": [float(value) for value in amounts],
        "total_cost_per_100g": float(np.dot(prices, amounts)),
    }
