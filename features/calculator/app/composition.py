"""Сценарий `/compute`: расчёт рецептуры вместе с долей от суточной нормы."""

from __future__ import annotations

from uuid import UUID

from .ports import DailyNorms
from .service import RecipeCalculator


class CompositionReport:
    """Отчёт калькулятора, дополненный суточными нормами.

    Расчёт без норм нужен рецептурам (метрики), поэтому нормы добавляются
    отдельным сценарием, а не внутри `RecipeCalculator.compute`.
    """

    def __init__(self, calculator: RecipeCalculator, norms: DailyNorms) -> None:
        self._calculator = calculator
        self._norms = norms

    async def compute(self, reference_protein_id: UUID, items: list[dict]) -> dict:
        result = await self._calculator.compute(reference_protein_id, items)
        result["daily_norms"] = await self._norms.for_recipe(
            macro=result["macro"],
            energy_kcal=result["energy_kcal"],
            micro=result["micro"],
            other=result["other"],
        )
        return result
