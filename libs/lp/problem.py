"""Постановка задачи линейного программирования и проверка входных данных.

Решается задача

    min cᵀx  при  A_ub·x ≤ b_ub,  A_eq·x = b_eq,  lower ≤ x ≤ upper,

границы переменных могут быть бесконечными. Ограничения «≥» приводятся к «≤»
умножением строки и правой части на −1 — это делает `make_problem`, чтобы
дальше весь модуль работал с одной формой записи.
"""

from dataclasses import dataclass

import numpy as np

INF = float("inf")

Matrix = np.ndarray
Vector = np.ndarray


class LpProblemError(ValueError):
    """Некорректная постановка задачи: размеры, NaN, бесконечности, l > u."""


@dataclass(frozen=True)
class LpProblem:
    """Задача ЛП в форме «≤» и «=» с границами переменных."""

    cost: Vector
    a_ub: Matrix
    b_ub: Vector
    a_eq: Matrix
    b_eq: Vector
    lower: Vector
    upper: Vector

    @property
    def variables(self) -> int:
        return int(self.cost.size)

    @property
    def rows(self) -> int:
        return int(self.a_ub.shape[0] + self.a_eq.shape[0])


def _as_vector(values, name: str) -> Vector:
    vector = np.asarray(values, dtype=float).ravel()
    if vector.size and not np.isfinite(vector).all():
        raise LpProblemError(f"{name}: допустимы только конечные числа")
    return vector


def _as_matrix(values, columns: int, name: str) -> Matrix:
    if values is None or len(values) == 0:
        return np.zeros((0, columns), dtype=float)
    matrix = np.asarray(values, dtype=float)
    if matrix.ndim == 1:
        matrix = matrix.reshape(1, -1)
    if matrix.ndim != 2:
        raise LpProblemError(f"{name}: ожидалась матрица")
    if matrix.shape[1] != columns:
        raise LpProblemError(f"{name}: {matrix.shape[1]} столбцов вместо {columns}")
    if matrix.size and not np.isfinite(matrix).all():
        raise LpProblemError(f"{name}: допустимы только конечные числа")
    return matrix


def _bounds(lower, upper, columns: int) -> tuple[Vector, Vector]:
    low = (
        np.full(columns, 0.0)
        if lower is None
        else np.asarray(lower, dtype=float).ravel()
    )
    high = (
        np.full(columns, INF)
        if upper is None
        else np.asarray(upper, dtype=float).ravel()
    )
    if low.size != columns or high.size != columns:
        raise LpProblemError("границы переменных не совпадают по размеру с c")
    if np.isnan(low).any() or np.isnan(high).any():
        raise LpProblemError("границы переменных не могут быть NaN")
    if (low == INF).any() or (high == -INF).any():
        raise LpProblemError("нижняя граница +inf или верхняя −inf недопустимы")
    if (low > high + 0.0).any():
        raise LpProblemError("нарушено условие lower ≤ upper")
    return low, high


def _rows(matrix: Matrix, vector: Vector, name: str) -> None:
    if matrix.shape[0] != vector.size:
        raise LpProblemError(
            f"{name}: {matrix.shape[0]} строк и {vector.size} правых частей"
        )


def make_problem(
    cost,
    *,
    a_ub=None,
    b_ub=None,
    a_eq=None,
    b_eq=None,
    a_lb=None,
    b_lb=None,
    lower=None,
    upper=None,
) -> LpProblem:
    """Собрать и проверить задачу; строки `a_lb·x ≥ b_lb` переводятся в «≤»."""
    vector_cost = _as_vector(cost, "c")
    columns = int(vector_cost.size)
    if columns == 0:
        raise LpProblemError("в задаче нет переменных")
    upper_matrix = _as_matrix(a_ub, columns, "A_ub")
    upper_rhs = _as_vector(b_ub, "b_ub") if b_ub is not None else np.zeros(0)
    greater = _as_matrix(a_lb, columns, "A_lb")
    greater_rhs = _as_vector(b_lb, "b_lb") if b_lb is not None else np.zeros(0)
    _rows(upper_matrix, upper_rhs, "A_ub")
    _rows(greater, greater_rhs, "A_lb")
    if greater.shape[0]:
        upper_matrix = np.vstack([upper_matrix, -greater])
        upper_rhs = np.concatenate([upper_rhs, -greater_rhs])
    equal = _as_matrix(a_eq, columns, "A_eq")
    equal_rhs = _as_vector(b_eq, "b_eq") if b_eq is not None else np.zeros(0)
    _rows(equal, equal_rhs, "A_eq")
    low, high = _bounds(lower, upper, columns)
    return LpProblem(
        cost=vector_cost,
        a_ub=upper_matrix,
        b_ub=upper_rhs,
        a_eq=equal,
        b_eq=equal_rhs,
        lower=low,
        upper=high,
    )
