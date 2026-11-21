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
