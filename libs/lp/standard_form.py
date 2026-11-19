"""Приведение задачи к рабочей форме: A·x = b, l ≤ x ≤ u.

Строки «≤» получают дополнительную переменную (slack) с границами [0, +∞),
строки «=» — вспомогательную переменную с границами [0, 0]. Благодаря этому
базис из добавленных переменных сразу единичный и двойственно допустимый:
фаза I не нужна.

Бесконечные границы заменяются «большим ящиком» ±`big_bound`. Если решение
опирается на такую границу, задача неограничена — это проверяется в
`dual_simplex` по маскам `box_lower` / `box_upper`.
"""

from dataclasses import dataclass

import numpy as np

from .problem import INF, LpProblem, Matrix, Vector

DEFAULT_BIG_BOUND = 1.0e9


@dataclass(frozen=True)
class StandardForm:
    """Задача в форме равенств с двусторонними границами всех переменных."""

    matrix: Matrix
    rhs: Vector
    cost: Vector
    lower: Vector
    upper: Vector
    box_lower: np.ndarray
    box_upper: np.ndarray
    structural: int
    basis: tuple[int, ...]

    @property
    def variables(self) -> int:
        return int(self.cost.size)

    @property
    def rows(self) -> int:
        return int(self.matrix.shape[0])


def _added_bounds(inequalities: int, equalities: int) -> tuple[Vector, Vector]:
    lower = np.zeros(inequalities + equalities)
    upper = np.concatenate([np.full(inequalities, INF), np.zeros(equalities)])
    return lower, upper


def _blocks(problem: LpProblem) -> tuple[Matrix, Vector]:
    inequalities = problem.a_ub.shape[0]
    equalities = problem.a_eq.shape[0]
    rows = inequalities + equalities
    original = np.vstack([problem.a_ub, problem.a_eq]) if rows else None
    if original is None:
        original = np.zeros((0, problem.variables))
    matrix = np.hstack([original, np.eye(rows)])
    rhs = np.concatenate([problem.b_ub, problem.b_eq])
    return matrix, rhs


def to_standard_form(
    problem: LpProblem, *, big_bound: float = DEFAULT_BIG_BOUND
) -> StandardForm:
    """Собрать рабочую форму задачи и начальный базис из добавленных переменных."""
    if big_bound <= 0 or not np.isfinite(big_bound):
        raise ValueError("big_bound должен быть конечным положительным числом")
    matrix, rhs = _blocks(problem)
    rows = matrix.shape[0]
    added_lower, added_upper = _added_bounds(
        problem.a_ub.shape[0], problem.a_eq.shape[0]
    )
    lower = np.concatenate([problem.lower, added_lower])
    upper = np.concatenate([problem.upper, added_upper])
    box_lower = lower == -INF
    box_upper = upper == INF
    lower = np.where(box_lower, -big_bound, lower)
    upper = np.where(box_upper, big_bound, upper)
    cost = np.concatenate([problem.cost, np.zeros(rows)])
    basis = tuple(range(problem.variables, problem.variables + rows))
    return StandardForm(
        matrix=matrix,
        rhs=rhs,
        cost=cost,
        lower=lower,
        upper=upper,
        box_lower=box_lower,
        box_upper=box_upper,
        structural=problem.variables,
        basis=basis,
    )
