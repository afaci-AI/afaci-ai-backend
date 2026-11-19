"""Результат решения задачи ЛП."""

from dataclasses import dataclass
from enum import Enum

import numpy as np

from .problem import Vector


class LpStatus(str, Enum):
    """Итог решения."""

    OPTIMAL = "optimal"
    INFEASIBLE = "infeasible"
    UNBOUNDED = "unbounded"
    ITERATION_LIMIT = "iteration_limit"


@dataclass(frozen=True)
class LpResult:
    """Решение задачи: статус, план, цель, двойственные оценки и базис.

    `basis` возвращается для тёплого старта: повторное решение задачи с
    другими правыми частями или границами начинается с него.
    `residual` — наибольшая из невязок ‖A·x − b‖∞ и нарушений границ.
    """

    status: LpStatus
    x: Vector | None
    objective: float | None
    duals: Vector | None
    basis: tuple[int, ...] | None
    iterations: int
    residual: float

    @property
    def is_optimal(self) -> bool:
        return self.status is LpStatus.OPTIMAL

    def value(self, default: float = float("nan")) -> float:
        return default if self.objective is None else self.objective


def failure(
    status: LpStatus,
    *,
    iterations: int,
    basis: tuple[int, ...] | None = None,
    residual: float = float("nan"),
) -> LpResult:
    """Результат без плана: недопустимость, неограниченность, лимит итераций."""
    return LpResult(
        status=status,
        x=None,
        objective=None,
        duals=None,
        basis=basis,
        iterations=iterations,
        residual=residual,
    )


def solution(
    x: Vector,
    *,
    cost: Vector,
    duals: Vector,
    basis: tuple[int, ...],
    iterations: int,
    residual: float,
) -> LpResult:
    """Оптимальный результат; цель считается по структурным переменным."""
    return LpResult(
        status=LpStatus.OPTIMAL,
        x=x,
        objective=float(np.dot(cost, x)),
        duals=duals,
        basis=basis,
        iterations=iterations,
        residual=residual,
    )
