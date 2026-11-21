"""Проверка входных данных поиска состава."""

from __future__ import annotations

import math

import numpy as np

from ..candidates import CandidateItem
from ..formulas import NAK_GROUPS
from .errors import RecipeOptimizationError


def is_finite(value) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(value)


def validate_data(candidates: list[CandidateItem], reference: dict) -> None:
    for group, _ in NAK_GROUPS:
        value = reference.get("values", {}).get(group)
        if not is_finite(value) or value <= 0:
            raise RecipeOptimizationError(
                f"В эталонном белке отсутствует положительное значение {group}."
            )
    for item in candidates:
        # compute_report uses zero only for absent chemical keys. Preserve that
        # policy for non-contributors; a known amino profile needs known protein.
        # An explicit NULL is still invalid and never replaced by the default.
        protein = item.chem.get("Массовая доля белка", None if item.amino else 0.0)
        if not is_finite(protein) or protein < 0:
            raise RecipeOptimizationError(
                f"Для «{item.name}» отсутствует корректное содержание белка."
            )
        for value in (*item.chem.values(), *item.amino.values()):
            if not is_finite(value) or value < 0:
                raise RecipeOptimizationError(
                    f"Для «{item.name}» есть пропущенные или некорректные данные состава."
                )
        # Match compute_report: a wholly absent profile is excluded from the
        # amino-acid calculation and reported as a warning, not invented as zero.
        # A present but incomplete profile still cannot support a valid search.
        if protein > 0 and item.amino:
            missing = [
                m for _, members in NAK_GROUPS for m in members if m not in item.amino
            ]
            if missing:
                raise RecipeOptimizationError(
                    f"Для «{item.name}» отсутствуют данные НАК: {', '.join(missing)}."
                )


def validate_request(
    candidates: list[CandidateItem], baseline_amounts: list[float], mode: str
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Проверяет запрос; возвращает (lower, upper, baseline, prices)."""
    if not candidates or len(candidates) != len(baseline_amounts):
        raise RecipeOptimizationError("Не передан исходный состав рецептуры.")
    if mode not in ("basic", "cost"):
        raise RecipeOptimizationError("Неизвестный режим оптимизации.")
    lower = np.array([c.min_amount_g for c in candidates], dtype=float)
    upper = np.array([c.max_amount_g for c in candidates], dtype=float)
    baseline = np.asarray(baseline_amounts, dtype=float)
    prices = np.array([c.price_per_kg / 1000 for c in candidates], dtype=float)
    if (
        not all(np.isfinite(v).all() for v in (lower, upper, baseline, prices))
        or np.any(lower < 0)
        or np.any(upper > 100)
        or np.any(lower > upper)
        or np.any(baseline < 0)
        or np.any(prices < 0)
        or abs(float(baseline.sum()) - 100) > 0.01
    ):
        raise RecipeOptimizationError("Некорректные массы, цены или диапазоны.")
    if float(lower.sum()) > 100 or float(upper.sum()) < 100:
        raise RecipeOptimizationError("В заданных диапазонах нельзя составить 100 г.")
    return lower, upper, baseline, prices
