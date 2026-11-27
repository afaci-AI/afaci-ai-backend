"""Сборка зависимостей продуктов: порты → SQL-реализации, аудит и вызывающий."""

from typing import Annotated

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from core.audit import resolve_food_user
from core.db.models import User
from core.db.session import get_db
from core.security import get_current_user_optional

from ..app import Caller, NutrientService, ProductImportService, ProductService
from ..infra.audit import FoodAuditLog, FoodNutrientSnapshots, FoodProductSnapshots
from ..infra.sql_repo import (
    SqlNutrientRepository,
    SqlProductRepository,
    SqlReferenceNames,
    SqlUnitOfWork,
)

Db = Annotated[AsyncSession, Depends(get_db)]


async def get_caller(
    authorization: Annotated[str | None, Header()] = None,
    current_user: Annotated[User | None, Depends(get_current_user_optional)] = None,
) -> Caller:
    """Метка участника для аудита определяется здесь, а не в сценариях."""
    return Caller(actor=resolve_food_user(current_user, authorization))


async def get_product_service(db: Db) -> ProductService:
    return ProductService(
        SqlProductRepository(db),
        SqlUnitOfWork(db),
        FoodAuditLog(),
        FoodProductSnapshots(),
    )


async def get_product_import_service(db: Db) -> ProductImportService:
    return ProductImportService(
        SqlProductRepository(db),
        SqlReferenceNames(db),
        SqlUnitOfWork(db),
        FoodAuditLog(),
        FoodProductSnapshots(),
    )


async def get_nutrient_service(db: Db) -> NutrientService:
    return NutrientService(
        SqlNutrientRepository(db),
        SqlUnitOfWork(db),
        FoodAuditLog(),
        FoodNutrientSnapshots(),
    )
