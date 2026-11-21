"""Двойственный симплекс-метод для переменных с двусторонними границами.

Все переменные рабочей формы ограничены с двух сторон, поэтому небазисная
переменная всегда стоит на той границе, которая отвечает знаку её оценки:
стартовый базис из добавленных переменных сразу двойственно допустим и фаза I
не нужна. На каждом шаге из базиса выводится переменная с наибольшим
нарушением своей границы, а входящая выбирается двойственным тестом отношений
с переходом небазисных переменных между границами (bound flipping).

Устойчивость: тест отношений Харриса (среди близких по отношению кандидатов
берётся наибольший по модулю ведущий элемент), правило Бленда после серии
вырожденных шагов (защита от зацикливания) и пересчёт разложения базиса при
росте невязки.
"""

from dataclasses import dataclass

import numpy as np

from .basis import Basis, SingularBasisError
from .problem import Vector
from .result import LpResult, LpStatus, failure, solution
from .standard_form import StandardForm

DEFAULT_TOL = 1.0e-9
BLAND_AFTER = 20
PIVOT_TOL = 1.0e-9
HARRIS_SLACK = 1.0e-7
INVERSE_ERROR_TOL = 1.0e-7
INVERSE_CHECK_EVERY = 10
BOX_TOL = 1.0e-6
RESIDUAL_TOL = 1.0e-6


@dataclass
class _Iterate:
    """Текущее состояние метода: базис и положение небазисных переменных."""

    form: StandardForm
    basis: Basis
    at_upper: np.ndarray
    is_basic: np.ndarray
    tol: float
    degenerate: int = 0

    @property
    def bland(self) -> bool:
        return self.degenerate > BLAND_AFTER


def _nonbasic_vector(state: _Iterate) -> Vector:
    values = np.where(state.at_upper, state.form.upper, state.form.lower)
    values[state.is_basic] = 0.0
    return values


def _basic_values(state: _Iterate) -> Vector:
    rhs = state.form.rhs - state.form.matrix @ _nonbasic_vector(state)
    return state.basis.ftran(rhs)


def _reduced_costs(state: _Iterate) -> tuple[Vector, Vector]:
    duals = state.basis.btran(state.form.cost[state.basis.indices])
    return state.form.cost - state.form.matrix.T @ duals, duals


def _leaving(state: _Iterate, basic: Vector) -> tuple[int, int, float] | None:
    """Выводимая переменная: наибольшее нарушение границы (или правило Бленда)."""
    indices = state.basis.indices
    below = state.form.lower[indices] - basic
    above = basic - state.form.upper[indices]
    violation = np.maximum(below, above)
    if violation.size == 0 or violation.max() <= state.tol:
        return None
    if state.bland:
        candidates = np.flatnonzero(violation > state.tol)
        position = int(min(candidates, key=lambda item: indices[item]))
    else:
        position = int(violation.argmax())
    direction = 1 if below[position] >= above[position] else -1
    return position, direction, float(violation[position])


def _eligible(state: _Iterate, row: Vector, direction: int) -> np.ndarray:
    """Небазисные переменные, движение которых уменьшает нарушение границы."""
    span = state.form.upper - state.form.lower
    movable = ~state.is_basic & (span > state.tol)
    may_rise = movable & ~state.at_upper
    may_fall = movable & state.at_upper
    if direction > 0:
        return (may_rise & (row < -PIVOT_TOL)) | (may_fall & (row > PIVOT_TOL))
    return (may_rise & (row > PIVOT_TOL)) | (may_fall & (row < -PIVOT_TOL))


def _harris_pick(
    row: Vector, columns: np.ndarray, ratios: np.ndarray, tol: float
) -> int:
    limit = ratios[0] * (1.0 + HARRIS_SLACK) + tol
    close = columns[ratios <= limit]
    return int(close[int(np.abs(row[close]).argmax())])


def _sorted_candidates(
    state: _Iterate, row: Vector, reduced: Vector, mask: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    columns = np.flatnonzero(mask)
    ratios = np.abs(reduced[columns]) / np.abs(row[columns])
    order = np.argsort(ratios, kind="stable")
    return columns[order], ratios[order]


def _ratio_test(
    state: _Iterate, row: Vector, reduced: Vector, direction: int, violation: float
) -> tuple[int, float, list[int]] | None:
    """Входящая переменная, её отношение и переброшенные между границами."""
    mask = _eligible(state, row, direction)
    if not mask.any():
        return None
    columns, ratios = _sorted_candidates(state, row, reduced, mask)
    if state.bland:
        position = int(columns.argmin())
        return int(columns[position]), float(ratios[position]), []
    flips: list[int] = []
    remaining = violation
    for position, column in enumerate(columns):
        span = state.form.upper[column] - state.form.lower[column]
        step = abs(row[column]) * span
        if step >= remaining - state.tol:
            entering = _harris_pick(
                row, columns[position:], ratios[position:], state.tol
            )
            return entering, float(ratios[position]), flips
        flips.append(int(column))
        remaining -= step
    return None


def _pivot(state: _Iterate, position: int, entering: int, flips: list[int]) -> None:
    for column in flips:
        state.at_upper[column] = not state.at_upper[column]
    column_image = state.basis.ftran(state.form.matrix[:, entering])
    leaving = state.basis.indices[position]
    state.basis.replace(position, entering, column_image)
    state.is_basic[leaving] = False
    state.is_basic[entering] = True


def _step(state: _Iterate, basic: Vector) -> LpStatus | None:
    """Одна итерация: вывод переменной, тест отношений, пересчёт базиса."""
    found = _leaving(state, basic)
    if found is None:
        return LpStatus.OPTIMAL
    position, direction, violation = found
    row = state.basis.tableau_row(position)
    reduced, _ = _reduced_costs(state)
    chosen = _ratio_test(state, row, reduced, direction, violation)
    if chosen is None:
        return LpStatus.INFEASIBLE
    entering, ratio, flips = chosen
    state.degenerate = state.degenerate + 1 if ratio <= state.tol else 0
    leaving = state.basis.indices[position]
    _pivot(state, position, entering, flips)
    state.at_upper[leaving] = direction < 0
    return None


def _run(state: _Iterate, max_iter: int) -> tuple[LpStatus, int, Vector]:
    basic = _basic_values(state)
    for iteration in range(max_iter):
        status = _step(state, basic)
        if status is not None:
            return status, iteration, basic
        stale = (iteration + 1) % INVERSE_CHECK_EVERY == 0
        if stale and state.basis.inverse_error() > INVERSE_ERROR_TOL:
            state.basis.refactor()
        basic = _basic_values(state)
    return LpStatus.ITERATION_LIMIT, max_iter, basic


def _full_vector(state: _Iterate, basic: Vector) -> Vector:
    values = _nonbasic_vector(state)
    values[state.basis.indices] = basic
    return np.clip(values, state.form.lower, state.form.upper)


def _residual(state: _Iterate, values: Vector) -> float:
    equations = state.form.matrix @ values - state.form.rhs
    low = state.form.lower - values
    high = values - state.form.upper
    parts = [np.abs(equations), low, high]
    return float(max(part.max(initial=0.0) for part in parts))


def _on_box(state: _Iterate, values: Vector) -> bool:
    """Решение опирается на искусственную границу «большого ящика»."""
    form = state.form
    high = form.box_upper & (values >= form.upper - BOX_TOL)
    low = form.box_lower & (values <= form.lower + BOX_TOL)
    return bool(high.any() or low.any())


def _finish(
    state: _Iterate, status: LpStatus, iterations: int, basic: Vector
) -> LpResult:
    values = _full_vector(state, basic)
    residual = _residual(state, values)
    basis = tuple(state.basis.indices)
    if status is not LpStatus.OPTIMAL:
        return failure(status, iterations=iterations, basis=basis, residual=residual)
    if _on_box(state, values):
        return failure(
            LpStatus.UNBOUNDED,
            iterations=iterations,
            basis=basis,
            residual=residual,
        )
    _, duals = _reduced_costs(state)
    structural = state.form.structural
    return solution(
        values[:structural],
        cost=state.form.cost[:structural],
        duals=duals,
        basis=basis,
        iterations=iterations,
        residual=residual,
    )


def _initial_state(form: StandardForm, indices: list[int], tol: float) -> _Iterate:
    basis = Basis(form.matrix, indices)
    is_basic = np.zeros(form.variables, dtype=bool)
    is_basic[indices] = True
    duals = basis.btran(form.cost[indices])
    reduced = form.cost - form.matrix.T @ duals
    at_upper = reduced < 0.0
    at_upper[is_basic] = False
    return _Iterate(
        form=form, basis=basis, at_upper=at_upper, is_basic=is_basic, tol=tol
    )


def _start_indices(form: StandardForm, warm_basis) -> list[int]:
    if warm_basis is None:
        return list(form.basis)
    indices = [int(item) for item in warm_basis]
    if len(indices) != form.rows or len(set(indices)) != len(indices):
        raise ValueError("warm_basis не соответствует числу строк задачи")
    if min(indices, default=0) < 0 or max(indices, default=0) >= form.variables:
        raise ValueError("warm_basis содержит несуществующий столбец")
    return indices


def minimize(
    form: StandardForm,
    *,
    warm_basis=None,
    tol: float = DEFAULT_TOL,
    max_iter: int | None = None,
) -> LpResult:
    """Решить задачу в рабочей форме двойственным симплекс-методом."""
    if tol <= 0:
        raise ValueError("tol должен быть положительным")
    limit = max_iter or max(1000, 50 * (form.rows + form.variables))
    indices = _start_indices(form, warm_basis)
    try:
        state = _initial_state(form, indices, tol)
    except SingularBasisError:
        state = _initial_state(form, list(form.basis), tol)
    status, iterations, basic = _run(state, limit)
    result = _finish(state, status, iterations, basic)
    if result.status is LpStatus.OPTIMAL and result.residual > RESIDUAL_TOL:
        state.basis.refactor()
        basic = _basic_values(state)
        result = _finish(state, status, iterations, basic)
    return result
