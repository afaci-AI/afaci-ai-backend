"""Модели ЛП для показателей качества: максимум БЦ и максимум t.

Цель «максимум БЦ» дробно-линейна: КРАС = (среднее(Cⱼ·B) − Cmin·B)/B, где
числитель и знаменатель — линейные формы масс. Преобразование Чарнса–Купера
убирает дробь: при y = x/B и s = 1/B нормировка B(y) = 1 оставляет в цели только
числитель, а исходные условия становятся линейными:

    Σpᵢyᵢ = 1,  Σyᵢ = 100·s,  lbᵢ·s ≤ yᵢ ≤ ubᵢ·s,  состав x = y/s

Вторичная цель «максимум t» (когда БЦ улучшить нельзя) использует вторую
нормировку — ΣNⱼ(z) = 1; тогда t = Cmin(z) и максимизируется напрямую, а предел
КРАС умножается на белковую базу, которая здесь осталась переменной.

Обе задачи решает двойственный симплекс-метод из `libs.lp`.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from libs.lp import INF, LpStatus, make_problem, solve

from .formulas.linear import LinearForms
from .lp_model import MIN_PROTEIN_BASE, TOTAL_MASS, LpModelInfeasible

# Предел масштабной переменной (s = 1/B, σ = 1/ΣNⱼ): обратная величина
# технического предела, ниже которого показатели не определены.
MAX_SCALE = 1.0 / MIN_PROTEIN_BASE


@dataclass(frozen=True)
class QualityBounds:
    """Пороги, которые нельзя ухудшать: КРАС ≤ kras_max, t ≥ t_min, белок."""

    kras_max: float | None = None
    t_min: float | None = None
    protein_min: float | None = None


@dataclass(frozen=True)
class _Model:
    """Собранная задача замены переменных: столбцы [переменные, масштаб, helper]."""

    cost: np.ndarray
    rows: list[np.ndarray]
    rhs: list[float]
    equalities: np.ndarray
    equality_rhs: list[float]
    lower: np.ndarray
    upper: np.ndarray


def greedy_maximum(weights: np.ndarray, lower: np.ndarray, upper: np.ndarray) -> float:
    """Максимум линейной формы при Σx = 100 и границах — жадно по весам."""
    amounts = np.asarray(lower, dtype=float).copy()
    free = TOTAL_MASS - float(amounts.sum())
    for index in np.argsort(-np.asarray(weights, dtype=float)):
        if free <= 0:
            break
        step = min(free, float(upper[index] - amounts[index]))
        if step > 0:
            amounts[index] += step
            free -= step
    return float(np.asarray(weights, dtype=float) @ amounts)


def _scale_lower(weights: np.ndarray, lower: np.ndarray, upper: np.ndarray) -> float:
    """Нижняя граница масштабной переменной: 1 / максимум нормирующей формы."""
    maximum = greedy_maximum(weights, lower, upper)
    return 1.0 / maximum if maximum > 0 else 0.0


def _blank(columns: int) -> np.ndarray:
    return np.zeros(columns, dtype=float)


def _coupling(
    lower: np.ndarray, upper: np.ndarray, columns: int, scale_at: int
) -> tuple[list[np.ndarray], list[float]]:
    """Диапазоны масс после замены: yᵢ ≤ ubᵢ·s и lbᵢ·s ≤ yᵢ."""
    rows: list[np.ndarray] = []
    for index, (low, high) in enumerate(zip(lower, upper, strict=True)):
        high_row = _blank(columns)
        high_row[index] = 1.0
        high_row[scale_at] = -float(high)
        rows.append(high_row)
        low_row = _blank(columns)
        low_row[index] = -1.0
        low_row[scale_at] = float(low)
        rows.append(low_row)
    return rows, [0.0] * len(rows)


def _quality(
    forms: LinearForms,
    bounds: QualityBounds,
    *,
    columns: int,
    scale_at: int,
    helper_at: int,
    base_is_one: bool,
) -> tuple[list[np.ndarray], list[float]]:
    """Строки порогов: helper ≤ Cⱼ·B, предел КРАС, t ≥ t₀ и белок.

    `base_is_one` — нормировка B = 1 (цель «максимум БЦ»): предел КРАС тогда
    стоит в правой части, иначе умножается на белковую базу.
    """
    count = forms.amino.shape[0]
    scores = forms.score_rows()
    rows: list[np.ndarray] = []
    rhs: list[float] = []
    for row in scores:
        line = _blank(columns)
        line[:count] = -row
        line[helper_at] = 1.0
        rows.append(line)
        rhs.append(0.0)
    if bounds.kras_max is not None:
        line = _blank(columns)
        line[:count] = scores.mean(axis=0)
        if not base_is_one:
            line[:count] -= float(bounds.kras_max) * forms.protein_base
        line[helper_at] = -1.0
        rows.append(line)
        rhs.append(float(bounds.kras_max) if base_is_one else 0.0)
    if bounds.t_min is not None:
        totals = forms.amino.sum(axis=1)
        for row in scores:
            line = _blank(columns)
            line[:count] = float(bounds.t_min) * totals - row
            rows.append(line)
            rhs.append(0.0)
    if bounds.protein_min is not None:
        line = _blank(columns)
        line[:count] = -forms.protein_macro
        line[scale_at] = TOTAL_MASS * float(bounds.protein_min)
        rows.append(line)
        rhs.append(0.0)
    return rows, rhs


def _assemble(
    forms: LinearForms,
    bounds: QualityBounds,
    *,
    lower: np.ndarray,
    upper: np.ndarray,
    normaliser: np.ndarray,
    objective: np.ndarray,
    base_is_one: bool,
) -> _Model:
    """Общая сборка: нормировка, сумма 100 г, диапазоны и пороги."""
    count = len(lower)
    columns = count + 2
    scale_at, helper_at = count, count + 1
    rows, rhs = _coupling(lower, upper, columns, scale_at)
    quality_rows, quality_rhs = _quality(
        forms,
        bounds,
        columns=columns,
        scale_at=scale_at,
        helper_at=helper_at,
        base_is_one=base_is_one,
    )
    normalisation = _blank(columns)
    normalisation[:count] = normaliser
    mass = _blank(columns)
    mass[:count] = 1.0
    mass[scale_at] = -TOTAL_MASS
    variable_lower = _blank(columns)
    variable_lower[scale_at] = _scale_lower(normaliser, lower, upper)
    variable_upper = np.full(columns, INF)
    variable_upper[scale_at] = MAX_SCALE
    return _Model(
        cost=objective,
        rows=rows + quality_rows,
        rhs=rhs + quality_rhs,
        equalities=np.vstack([normalisation, mass]),
        equality_rhs=[1.0, 0.0],
        lower=variable_lower,
        upper=variable_upper,
    )


def _solve(model: _Model) -> np.ndarray:
    problem = make_problem(
        model.cost,
        a_ub=np.array(model.rows).reshape(len(model.rows), len(model.cost)),
        b_ub=np.array(model.rhs, dtype=float),
        a_eq=model.equalities,
        b_eq=model.equality_rhs,
        lower=model.lower,
        upper=model.upper,
    )
    result = solve(problem)
    if result.status is not LpStatus.OPTIMAL or result.x is None:
        raise LpModelInfeasible(result.status.value)
    return np.asarray(result.x, dtype=float)


def _restore(solution: np.ndarray, count: int) -> np.ndarray:
    """Состав x = y/s из переменных замены; масштаб положителен по построению."""
    scale = float(solution[count])
    if scale <= 0:
        raise LpModelInfeasible("масштабная переменная вышла на ноль")
    return np.asarray(solution[:count], dtype=float) / scale


def maximum_bc(
    forms: LinearForms,
    *,
    lower: np.ndarray,
    upper: np.ndarray,
    bounds: QualityBounds,
) -> tuple[np.ndarray, float]:
    """Состав с максимальной БЦ и сама БЦ (из цели задачи).

    Цель задачи — минимум КРАС: среднее(Cⱼ) − Cmin при нормировке B = 1.
    """
    count = len(lower)
    objective = _blank(count + 2)
    objective[:count] = forms.score_rows().mean(axis=0)
    objective[count + 1] = -1.0
    model = _assemble(
        forms,
        bounds,
        lower=lower,
        upper=upper,
        normaliser=forms.protein_base,
        objective=objective,
        base_is_one=True,
    )
    solution = _solve(model)
    return _restore(solution, count), 100.0 - float(objective @ solution)


def maximum_t(
    forms: LinearForms,
    *,
    lower: np.ndarray,
    upper: np.ndarray,
    bounds: QualityBounds,
) -> tuple[np.ndarray, float]:
    """Состав с максимальным t и само t (при нормировке ΣNⱼ = 1 это Cmin)."""
    count = len(lower)
    objective = _blank(count + 2)
    objective[count + 1] = -1.0
    model = _assemble(
        forms,
        bounds,
        lower=lower,
        upper=upper,
        normaliser=forms.amino.sum(axis=1),
        objective=objective,
        base_is_one=False,
    )
    solution = _solve(model)
    return _restore(solution, count), float(solution[count + 1])
