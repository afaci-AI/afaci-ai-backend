"""Оптимизация стоимости рецептуры методом SLSQP (scipy).

Чистая вычислительная логика без обращения к БД. Задача: найти долевой состав
рецептуры (Xᵢ, г / 100 г), минимизирующий суммарную стоимость сырья при
заданных ограничениях на качество белка (БЦ, КРАС).
"""

from __future__ import annotations

import numpy as np
from scipy.optimize import Bounds, minimize

from .candidates import CandidateItem, CostOptimizationConstraints, build_items
from .exceptions import OptimizationInfeasibleError
from .formulas import compute_report

N_RESTARTS = 6


def _random_feasible_start(
    candidates: list[CandidateItem],
    rng: np.random.Generator,
) -> np.ndarray:
    """Случайная начальная точка, удовлетворяющая sum=100 и bounds (приближённо)."""
    n = len(candidates)
    lb = np.array([c.min_amount_g for c in candidates])
    ub = np.array([c.max_amount_g for c in candidates])
    # Случайный вектор на основе Dirichlet + сдвиг в lb
    alpha = rng.random(n) + 0.1
    dirichlet = rng.dirichlet(alpha)
    total_free = 100.0 - lb.sum()
    x0 = lb + dirichlet * total_free
    # Обрезать по ub и перераспределить остаток
    x0 = np.clip(x0, lb, ub)
    deficit = 100.0 - x0.sum()
    if abs(deficit) > 1e-6:
        slack = ub - x0
        total_slack = slack.sum()
        if total_slack > 1e-9:
            x0 += slack / total_slack * deficit
    return np.clip(x0, lb, ub)


def _uniform_start(candidates: list[CandidateItem]) -> np.ndarray:
    """Начальная точка: 100 г обратно пропорционально цене (дешёвые получают больше)."""
    lb = np.array([c.min_amount_g for c in candidates])
    ub = np.array([c.max_amount_g for c in candidates])
    prices = np.array([c.price_per_kg for c in candidates], dtype=float)
    inv = 1.0 / (prices + 1e-9)
    total_free = 100.0 - lb.sum()
    x0 = lb + inv / inv.sum() * total_free
    return np.clip(x0, lb, ub)


def _check_bounds(lb: np.ndarray, ub: np.ndarray) -> None:
    """Ранняя проверка допустимости по границам."""
    if lb.sum() > 100.0 + 1e-6:
        raise OptimizationInfeasibleError(
            f"Сумма нижних границ Xᵢ ({lb.sum():.2f} г) превышает 100 г."
        )
    if ub.sum() < 100.0 - 1e-6:
        raise OptimizationInfeasibleError(
            f"Сумма верхних границ Xᵢ ({ub.sum():.2f} г) меньше 100 г."
        )


def _quality_constraints(
    candidates: list[CandidateItem],
    reference: dict,
    constraints: CostOptimizationConstraints,
) -> list[dict]:
    """Неравенства SLSQP по качеству белка: БЦ ≥ bc_min, КРАС ≤ kras_max."""
    result: list[dict] = []

    if constraints.bc_min is not None:
        bc_min = float(constraints.bc_min)

        def bc_constraint(x: np.ndarray) -> float:
            try:
                report = compute_report(build_items(candidates, x), reference)
                return (report["quality"]["bc"] or 0.0) - bc_min
            except Exception:  # noqa: BLE001
                return -1.0

        result.append({"type": "ineq", "fun": bc_constraint})

    if constraints.kras_max is not None:
        kras_max = float(constraints.kras_max)

        def kras_constraint(x: np.ndarray) -> float:
            try:
                report = compute_report(build_items(candidates, x), reference)
                return kras_max - (report["quality"]["kras"] or 999.0)
            except Exception:  # noqa: BLE001
                return -1.0

        result.append({"type": "ineq", "fun": kras_constraint})
    return result


def _solve(
    candidates: list[CandidateItem],
    prices: np.ndarray,
    bounds: Bounds,
    constraints: list[dict],
):
    """Несколько запусков SLSQP из разных стартов; лучший успешный результат."""

    def objective(x: np.ndarray) -> float:
        return float(np.dot(prices, x))

    def objective_jac(x: np.ndarray) -> np.ndarray:
        return prices

    rng = np.random.default_rng(42)
    best = None
    for i in range(N_RESTARTS):
        x0 = (
            _uniform_start(candidates)
            if i == 0
            else _random_feasible_start(candidates, rng)
        )
        try:
            res = minimize(
                objective,
                x0,
                method="SLSQP",
                jac=objective_jac,
                bounds=bounds,
                constraints=constraints,
                options={"ftol": 1e-9, "maxiter": 500, "disp": False},
            )
            if res.success and (best is None or res.fun < best.fun):
                best = res
        except Exception:  # noqa: BLE001, S112
            continue
    return best


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

    n = len(candidates)
    lb = np.array([c.min_amount_g for c in candidates])
    ub = np.array([c.max_amount_g for c in candidates])
    _check_bounds(lb, ub)

    prices = np.array([c.price_per_kg / 1000.0 for c in candidates])  # сом/г
    slsqp_constraints: list[dict] = [
        {"type": "eq", "fun": lambda x: np.sum(x) - 100.0, "jac": lambda x: np.ones(n)},
        *_quality_constraints(candidates, reference, constraints),
    ]
    best = _solve(candidates, prices, Bounds(lb=lb, ub=ub), slsqp_constraints)

    if best is None or not best.success:
        raise OptimizationInfeasibleError(
            "SLSQP не нашёл допустимого решения после нескольких попыток. "
            "Попробуйте ослабить ограничения по качеству или расширить диапазоны Xᵢ."
        )

    amounts = [round(float(v), 4) for v in best.x]
    total_cost = float(np.dot(prices, best.x))
    return {"amounts": amounts, "total_cost_per_100g": total_cost}
