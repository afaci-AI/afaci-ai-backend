"""Режимы поиска состава как стратегии.

Режим отвечает на пять вопросов: нужен ли нижний предел белка, какую задачу ЛП
решать, какой из проверенных составов лучше, в чём измеряется улучшение против
исходной рецептуры и какие поля стоимости попадают в ответ. Новый режим — это
ещё один класс и запись в `MODES`; `optimizer`, `search`, `result` и
`validation` при этом не меняются.
"""

from __future__ import annotations

from typing import Protocol

import numpy as np

from ..candidates import CandidateItem
from ..formulas.linear import LinearForms
from .errors import PER_KILOGRAM
from .lp_basic import solve_basic
from .lp_cost import protein_floor, solve_cost
from .recipe import EvaluatedRecipe

COST_FIELDS = (
    "baseline_cost_per_100g",
    "total_cost_per_100g",
    "cost_change_per_100g",
    "savings_per_100g",
    "baseline_cost_per_kg",
    "total_cost_per_kg",
    "cost_change_per_kg",
    "savings_per_kg",
    "savings_percent",
)


class OptimizationMode(Protocol):
    """Чем один режим поиска состава отличается от другого."""

    name: str

    def protein_min(self, forms: LinearForms, baseline: np.ndarray) -> float | None:
        """Нижний предел массовой доли белка либо None, если он не нужен."""

    def solve(
        self,
        forms: LinearForms,
        *,
        lower: np.ndarray,
        upper: np.ndarray,
        prices: np.ndarray,
        original: dict,
        baseline: np.ndarray,
        tolerance: float,
    ) -> np.ndarray | None:
        """Решение задачи режима; None — задача недопустима."""

    def rank(self, entry: EvaluatedRecipe) -> float:
        """Чем меньше, тем лучше состав для этого режима."""

    def improvement(
        self, entry: EvaluatedRecipe, *, base_cost: float, margins: np.ndarray
    ) -> float:
        """Насколько состав лучше исходного по цели режима."""

    def price(self, candidate: CandidateItem) -> float | None:
        """Цена позиции в ответе либо None, если режим её не показывает."""

    def summary(self, *, base_cost: float, cost: float) -> dict:
        """Поля стоимости в ответе; ключи одни и те же во всех режимах."""


class BasicMode:
    """Максимум биологической ценности; стоимость не учитывается."""

    name = "basic"

    def protein_min(self, forms: LinearForms, baseline: np.ndarray) -> float | None:
        return None

    def solve(
        self,
        forms: LinearForms,
        *,
        lower: np.ndarray,
        upper: np.ndarray,
        prices: np.ndarray,
        original: dict,
        baseline: np.ndarray,
        tolerance: float,
    ) -> np.ndarray | None:
        return solve_basic(
            forms, lower=lower, upper=upper, original=original, tolerance=tolerance
        )

    def rank(self, entry: EvaluatedRecipe) -> float:
        return -entry.quality["bc"]

    def improvement(
        self, entry: EvaluatedRecipe, *, base_cost: float, margins: np.ndarray
    ) -> float:
        return float(margins.max())

    def price(self, candidate: CandidateItem) -> float | None:
        return None

    def summary(self, *, base_cost: float, cost: float) -> dict:
        return dict.fromkeys(COST_FIELDS)


class CostMode:
    """Минимум стоимости при качестве белка не хуже исходного."""

    name = "cost"

    def protein_min(self, forms: LinearForms, baseline: np.ndarray) -> float | None:
        # Нижний предел белка нужен только здесь: минимум стоимости уводил
        # белок к нулю, показатели качества этого не замечают.
        return protein_floor(forms, baseline)

    def solve(
        self,
        forms: LinearForms,
        *,
        lower: np.ndarray,
        upper: np.ndarray,
        prices: np.ndarray,
        original: dict,
        baseline: np.ndarray,
        tolerance: float,
    ) -> np.ndarray | None:
        return solve_cost(
            forms,
            lower=lower,
            upper=upper,
            prices=prices,
            original=original,
            baseline=baseline,
        )

    def rank(self, entry: EvaluatedRecipe) -> float:
        return entry.cost

    def improvement(
        self, entry: EvaluatedRecipe, *, base_cost: float, margins: np.ndarray
    ) -> float:
        return base_cost - entry.cost

    def price(self, candidate: CandidateItem) -> float | None:
        return candidate.price_per_kg

    def summary(self, *, base_cost: float, cost: float) -> dict:
        savings = base_cost - cost
        return {
            # Поля `*_per_100g` устарели: оставлены для выпущенных клиентов.
            "baseline_cost_per_100g": base_cost,
            "total_cost_per_100g": cost,
            "cost_change_per_100g": -savings,
            "savings_per_100g": savings,
            "baseline_cost_per_kg": base_cost * PER_KILOGRAM,
            "total_cost_per_kg": cost * PER_KILOGRAM,
            "cost_change_per_kg": -savings * PER_KILOGRAM,
            "savings_per_kg": savings * PER_KILOGRAM,
            "savings_percent": savings / base_cost * 100 if base_cost != 0 else None,
        }


MODES: dict[str, OptimizationMode] = {
    mode.name: mode for mode in (BasicMode(), CostMode())
}
