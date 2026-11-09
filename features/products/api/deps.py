"""Сборка зависимостей продуктов: порты → SQL-реализации и аудит."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.session import get_db

from ..app import NutrientService, ProductService
from ..infra.audit import FoodAuditTrail
from ..infra.sql_repo import SqlNutrientRepository, SqlProductRepository


async def get_product_service(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProductService:
    return ProductService(SqlProductRepository(db), FoodAuditTrail())


async def get_nutrient_service(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> NutrientService:
    return NutrientService(SqlNutrientRepository(db), FoodAuditTrail())
