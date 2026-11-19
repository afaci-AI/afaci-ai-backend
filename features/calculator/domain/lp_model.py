"""Модель линейного программирования для оптимизации состава.

Переменные — массы ингредиентов x (г / 100 г) и вспомогательная w, равная
Cmin·B в оптимуме. Через w ограничение «КРАС ≤ K» записывается линейно:

    w ≤ Cⱼ·B для всех j,   (1/n)·Σⱼ Cⱼ·B − w ≤ K·B

Любое допустимое (x, w) даёт КРАС = среднее(Cⱼ) − Cmin ≤ среднее(Cⱼ) − w ≤ K,
а при w = Cmin·B неравенство обращается в исходное, то есть запись точная.
Ограничение по утилитарности и сопоставимой избыточности сводится к одному
условию t ≥ t₀ (связь U и G с t — в `formulas/linear.py`), которое после
умножения на B > 0 тоже линейно:

    100·Nⱼ/rⱼ ≥ t₀·Σₖ Nₖ для всех j

Решает модель собственный двойственный симплекс-метод из `libs.lp`.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from libs.lp import LpStatus, make_problem, solve

from .formulas.linear import LinearForms

# Технический предел белковой базы: ниже него скоры не определены (решение 4
# этапа 3, см. plan/backend.md).
MIN_PROTEIN_BASE = 1.0e-6
TOTAL_MASS = 100.0
# Запас для искусственной верхней границы w: она не должна отсекать оптимум.
WEIGHT_MARGIN = 1.0 + 1.0e-6


class LpModelInfeasible(Exception):
    """Модель не имеет допустимого решения (доказано симплекс-методом)."""


@dataclass(frozen=True)
class QualityTargets:
    """Пороги качества в виде, пригодном для линейной записи.

    `kras_max` — верхний предел КРАС (БЦ ≥ 100 − kras_max), `t_min` — нижний
    предел t = Cmin/ΣMⱼ, через который выражаются U и G, `protein_min` —
    массовая доля белка рецептуры, г / 100 г.
    """

    kras_max: float | None = None
    t_min: float | None = None
    protein_min: float | None = None


def t_floor(
    forms: LinearForms, *, u_min: float | None, g_max: float | None
) -> float | None:
    """Нижний предел t, обеспечивающий U ≥ u_min и G ≤ g_max.

    U = R·t/100 и G = 100/t − R, обе зависимости монотонны по t, поэтому пара
    порогов сводится к одному: t ≥ max(100·u_min/R, 100/(g_max + R)).
    """
    reference_sum = forms.reference_sum
    if reference_sum <= 0:
        return None
    floors = []
    if u_min is not None:
        floors.append(100.0 * float(u_min) / reference_sum)
    if g_max is not None and float(g_max) + reference_sum > 0:
        floors.append(100.0 / (float(g_max) + reference_sum))
    return max(floors) if floors else None


def weight_bound(forms: LinearForms, upper: np.ndarray) -> float:
    """Верхняя граница w = Cmin·B: минимум по группам от максимума Cⱼ·B.

    Каждая строка Cⱼ·B = 100·Nⱼ/rⱼ максимальна при массах по верхним границам,
    а w не превосходит любой из строк, значит и минимума их максимумов.
    """
    if forms.group_count == 0:
        return 0.0
    rows = forms.score_rows()
    best = np.maximum(rows, 0.0) @ np.asarray(upper, dtype=float)
    return float(max(best.min(), 0.0)) * WEIGHT_MARGIN


def _kras_row(forms: LinearForms, kras_max: float) -> tuple[np.ndarray, float]:
    """Строка «(1/n)·Σⱼ Cⱼ·B − w ≤ KРАС_max·B»."""
    rows = forms.score_rows()
    coefficients = rows.mean(axis=0) - float(kras_max) * forms.protein_base
    return np.append(coefficients, -1.0), 0.0


def _min_score_rows(forms: LinearForms) -> list[np.ndarray]:
    """Строки «w ≤ Cⱼ·B»."""
    return [np.append(-row, 1.0) for row in forms.score_rows()]


def _t_rows(forms: LinearForms, t_min: float) -> list[np.ndarray]:
    """Строки «t₀·Σₖ Nₖ − 100·Nⱼ/rⱼ ≤ 0»."""
    totals = forms.amino.sum(axis=1)
    return [np.append(float(t_min) * totals - row, 0.0) for row in forms.score_rows()]


def build_problem(
    forms: LinearForms,
    *,
    lower: np.ndarray,
    upper: np.ndarray,
    prices: np.ndarray,
    targets: QualityTargets,
):
    """Задача ЛП: min Σ(ценаᵢ·xᵢ) при Σx = 100, границах и порогах качества."""
    count = len(lower)
    rows: list[np.ndarray] = []
    rhs: list[float] = []

    def add(row: np.ndarray, value: float) -> None:
        rows.append(row)
        rhs.append(value)

    if forms.group_count and targets.kras_max is not None:
        row, value = _kras_row(forms, targets.kras_max)
        add(row, value)
        for score_row in _min_score_rows(forms):
            add(score_row, 0.0)
    if forms.group_count and targets.t_min is not None:
        for score_row in _t_rows(forms, targets.t_min):
            add(score_row, 0.0)
    if targets.protein_min is not None:
        add(
            np.append(-forms.protein_macro, 0.0),
            -TOTAL_MASS * float(targets.protein_min),
        )
    if forms.protein_base.any():
        add(np.append(-forms.protein_base, 0.0), -MIN_PROTEIN_BASE)

    cost = np.append(np.asarray(prices, dtype=float), 0.0)
    equality = np.append(np.ones(count), 0.0).reshape(1, count + 1)
    return make_problem(
        cost,
        a_ub=np.array(rows).reshape(len(rows), count + 1) if rows else None,
        b_ub=np.array(rhs, dtype=float) if rows else None,
        a_eq=equality,
        b_eq=[TOTAL_MASS],
        lower=np.append(np.asarray(lower, dtype=float), 0.0),
        upper=np.append(np.asarray(upper, dtype=float), weight_bound(forms, upper)),
    )


def solve_amounts(
    forms: LinearForms,
    *,
    lower: np.ndarray,
    upper: np.ndarray,
    prices: np.ndarray,
    targets: QualityTargets,
) -> np.ndarray:
    """Массы минимальной стоимости, удовлетворяющие порогам качества.

    Бросает `LpModelInfeasible`, если таких масс нет: двойственный
    симплекс-метод доказывает это, а не просто не находит решение.
    """
    problem = build_problem(
        forms, lower=lower, upper=upper, prices=prices, targets=targets
    )
    result = solve(problem)
    if result.status is not LpStatus.OPTIMAL or result.x is None:
        raise LpModelInfeasible(result.status.value)
    amounts = np.asarray(result.x[: len(lower)], dtype=float)
    return np.clip(amounts, lower, upper)
