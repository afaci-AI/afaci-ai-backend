"""Геометрия допустимого множества: сумма 100 г и границы по ингредиентам."""

from __future__ import annotations

import numpy as np


def project(values: np.ndarray, lower: np.ndarray, upper: np.ndarray) -> np.ndarray:
    """Euclidean projection onto the bounded simplex (exact sum, no rounding)."""
    lo = float(np.min(values - upper)) - 100.0
    hi = float(np.max(values - lower)) + 100.0
    for _ in range(80):
        midpoint = (lo + hi) / 2
        if np.clip(values - midpoint, lower, upper).sum() > 100:
            lo = midpoint
        else:
            hi = midpoint
    result = np.clip(values - (lo + hi) / 2, lower, upper)
    for i in range(len(result)):
        difference = 100.0 - float(result.sum())
        result[i] += np.clip(difference, lower[i] - result[i], upper[i] - result[i])
    return result


def build_starts(
    baseline: np.ndarray,
    lower: np.ndarray,
    upper: np.ndarray,
    prices: np.ndarray,
    mode: str,
) -> list[np.ndarray]:
    """Стартовые точки: исходный состав, равные доли, 5 случайных, самый дешёвый."""
    n = len(baseline)
    rng = np.random.default_rng(42)
    starts = [
        project(baseline, lower, upper),
        project(np.full(n, 100 / n), lower, upper),
    ]
    for _ in range(5):
        starts.append(project(rng.dirichlet(np.ones(n)) * 100, lower, upper))
    if mode == "cost":
        cheapest = lower.copy()
        for index in np.argsort(prices):
            cheapest[index] += min(upper[index] - cheapest[index], 100 - cheapest.sum())
        starts.append(cheapest)
    return starts
