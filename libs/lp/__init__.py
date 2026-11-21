"""Задачи линейного программирования: собственный двойственный симплекс-метод.

    from libs.lp import make_problem, solve

    problem = make_problem([1, 2], a_ub=[[-1, -1]], b_ub=[-3], upper=[5, 5])
    result = solve(problem)
    result.status, result.x, result.objective

Сторонние решатели ЛП (`scipy.optimize.linprog`, HiGHS, PuLP, OR-Tools, cvxpy)
не используются: метод реализован в этом пакете. NumPy нужен только как
линейная алгебра.
"""

from .problem import INF, LpProblem, LpProblemError, make_problem
from .result import LpResult, LpStatus
from .standard_form import DEFAULT_BIG_BOUND, StandardForm, to_standard_form

__all__ = [
    "DEFAULT_BIG_BOUND",
    "INF",
    "LpProblem",
    "LpProblemError",
    "LpResult",
    "LpStatus",
    "StandardForm",
    "make_problem",
    "solve",
    "to_standard_form",
]


def solve(
    problem: LpProblem,
    *,
    warm_basis=None,
    tol: float = 1.0e-9,
    max_iter: int | None = None,
    big_bound: float = DEFAULT_BIG_BOUND,
) -> LpResult:
    """Решить задачу ЛП: min cᵀx при A_ub·x ≤ b_ub, A_eq·x = b_eq, l ≤ x ≤ u.

    `warm_basis` — базис из прежнего результата (`LpResult.basis`): тёплый
    старт после изменения правых частей или границ. `big_bound` заменяет
    бесконечные границы переменных; если решение опирается на эту границу,
    возвращается статус `unbounded`.
    """
    from .dual_simplex import minimize

    form = to_standard_form(problem, big_bound=big_bound)
    return minimize(form, warm_basis=warm_basis, tol=tol, max_iter=max_iter)
