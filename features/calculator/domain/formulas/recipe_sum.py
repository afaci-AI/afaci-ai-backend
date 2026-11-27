"""Правило методики: масса ингредиентов рецептуры — ровно 100 г."""

from __future__ import annotations

from collections.abc import Iterable

from ..exceptions import EmptyRecipeError, InvalidRecipeSumError
from .constants import REQUIRED_SUM, SUM_TOLERANCE


def validate_recipe_sum(amounts: Iterable[float]) -> None:
    """EmptyRecipeError без ингредиентов; InvalidRecipeSumError, если сумма Xᵢ
    отличается от 100 г больше допуска."""
    amounts = list(amounts)
    if not amounts:
        raise EmptyRecipeError("Список ингредиентов пуст.")
    total = sum(amounts)
    if abs(total - REQUIRED_SUM) > SUM_TOLERANCE:
        raise InvalidRecipeSumError(total, REQUIRED_SUM)
