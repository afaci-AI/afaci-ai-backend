"""Сборка зависимостей калькулятора: порты → SQL-реализация (composition root)."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.session import get_db

from ..app import RecipeCalculator, ReferenceCatalog
from ..infra.sql_reader import SqlCalculatorData


async def get_calculator(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RecipeCalculator:
    data = SqlCalculatorData(db)
    return RecipeCalculator(references=data, products=data)


async def get_reference_catalog(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ReferenceCatalog:
    return SqlCalculatorData(db)


async def compute_recipe_in_session(
    db: AsyncSession, reference_id, items: list[dict]
) -> dict:
    """Расчёт для кода, у которого уже есть сессия БД (сохранение рецептур)."""
    data = SqlCalculatorData(db)
    return await RecipeCalculator(data, data).compute(reference_id, items)
