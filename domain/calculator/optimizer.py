"""
Оптимизация стоимости рецептуры методом SLSQP (scipy).

Чистая вычислительная логика без обращения к БД.
Задача: найти долевой состав рецептуры (Xᵢ, г / 100 г),
минимизирующий суммарную стоимость сырья при заданных
ограничениях на качество белка (БЦ, КРАС).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.optimize import Bounds, minimize

from domain.calculator.exceptions import OptimizationInfeasibleError
from domain.calculator.formulas import compute_report


@dataclass
class CandidateItem:
    product_id: str
    name: str
    chem: dict
    amino: dict
    price_per_kg: float
    min_amount_g: float = 0.0
    max_amount_g: float = 100.0
    region: str | None = None
    subcategory: str | None = None


@dataclass
class CostOptimizationConstraints:
    bc_min: float | None = None  # БЦ ≥ bc_min
    kras_max: float | None = None  # КРАС ≤ kras_max


def _build_items(candidates: list[CandidateItem], x: np.ndarray) -> list[dict]:
    return [
        {
            "product_id": c.product_id,
            "name": c.name,
            "region": c.region,
            "subcategory": c.subcategory,
            "amount_g": float(x[i]),
            "chem": c.chem,
            "amino": c.amino,
        }
        for i, c in enumerate(candidates)
    ]


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
    """Начальная точка: распределяем 100 г обратно пропорционально цене (дешёвые получают больше)."""
    lb = np.array([c.min_amount_g for c in candidates])
    ub = np.array([c.max_amount_g for c in candidates])
    prices = np.array([c.price_per_kg for c in candidates], dtype=float)
    inv = 1.0 / (prices + 1e-9)
    total_free = 100.0 - lb.sum()
    x0 = lb + inv / inv.sum() * total_free
    return np.clip(x0, lb, ub)


def optimize_cost(
    candidates: list[CandidateItem],
    reference: dict,
    constraints: CostOptimizationConstraints,
) -> dict:
    """
    Находит состав рецептуры с минимальной стоимостью.

    Возвращает {"amounts": list[float], "total_cost_per_100g": float}.
    Бросает OptimizationInfeasibleError если задача неразрешима.
    """
    if not candidates:
        raise OptimizationInfeasibleError("Список кандидатов пуст.")

    n = len(candidates)
    lb = np.array([c.min_amount_g for c in candidates])
    ub = np.array([c.max_amount_g for c in candidates])

    # Ранняя проверка feasibility по bounds
    if lb.sum() > 100.0 + 1e-6:
        raise OptimizationInfeasibleError(
            f"Сумма нижних границ Xᵢ ({lb.sum():.2f} г) превышает 100 г."
        )
    if ub.sum() < 100.0 - 1e-6:
        raise OptimizationInfeasibleError(
            f"Сумма верхних границ Xᵢ ({ub.sum():.2f} г) меньше 100 г."
        )

    prices = np.array([c.price_per_kg / 1000.0 for c in candidates])  # сом/г

    def objective(x: np.ndarray) -> float:
        return float(np.dot(prices, x))

    def objective_jac(x: np.ndarray) -> np.ndarray:
        return prices

    bounds = Bounds(lb=lb, ub=ub)

    slsqp_constraints: list[dict] = [
        {"type": "eq", "fun": lambda x: np.sum(x) - 100.0, "jac": lambda x: np.ones(n)},
    ]

    if constraints.bc_min is not None:
        bc_min = float(constraints.bc_min)

        def _bc_con(x: np.ndarray) -> float:
            try:
                report = compute_report(_build_items(candidates, x), reference)
                return (report["quality"]["bc"] or 0.0) - bc_min
            except Exception:  # noqa: BLE001
                return -1.0

        slsqp_constraints.append({"type": "ineq", "fun": _bc_con})

    if constraints.kras_max is not None:
        kras_max = float(constraints.kras_max)

        def _kras_con(x: np.ndarray) -> float:
            try:
                report = compute_report(_build_items(candidates, x), reference)
                return kras_max - (report["quality"]["kras"] or 999.0)
            except Exception:  # noqa: BLE001
                return -1.0

        slsqp_constraints.append({"type": "ineq", "fun": _kras_con})

    rng = np.random.default_rng(42)
    best_result = None
    N_RESTARTS = 6

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
                constraints=slsqp_constraints,
                options={"ftol": 1e-9, "maxiter": 500, "disp": False},
            )
            if res.success and (best_result is None or res.fun < best_result.fun):
                best_result = res
        except Exception:  # noqa: BLE001, S112
            continue

    if best_result is None or not best_result.success:
        raise OptimizationInfeasibleError(
            "SLSQP не нашёл допустимого решения после нескольких попыток. "
            "Попробуйте ослабить ограничения по качеству или расширить диапазоны Xᵢ."
        )

    amounts = [round(float(v), 4) for v in best_result.x]
    total_cost = float(np.dot(prices, best_result.x))

    return {"amounts": amounts, "total_cost_per_100g": total_cost}
