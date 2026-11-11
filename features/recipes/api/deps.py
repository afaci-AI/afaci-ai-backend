"""Сборка зависимостей рецептур: порты → SQL-реализация и калькулятор."""

from typing import Annotated
from uuid import UUID

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.session import get_db
from features.calculator.api.deps import get_calculator
from features.calculator.app import RecipeCalculator

from ..app import RecipeService
from ..infra.sql_repo import SqlRecipeRepository


class _CalculatorAdapter:
    """Метрики рецептуры считает калькулятор через его публичный сервис."""

    def __init__(self, calculator: RecipeCalculator) -> None:
        self._calculator = calculator

    async def compute(self, reference_protein_id: UUID, items: list[dict]) -> dict:
        return await self._calculator.compute(reference_protein_id, items)


async def get_recipe_service(
    db: Annotated[AsyncSession, Depends(get_db)],
    calculator: Annotated[RecipeCalculator, Depends(get_calculator)],
) -> RecipeService:
    return RecipeService(SqlRecipeRepository(db), _CalculatorAdapter(calculator))
