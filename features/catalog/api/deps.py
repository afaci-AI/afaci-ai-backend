"""Сборка зависимостей справочников: порт → SQL-реализация."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.session import get_db

from ..app import CatalogService
from ..infra.sql_repo import SqlCatalogRepository


async def get_catalog_service(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CatalogService:
    return CatalogService(SqlCatalogRepository(db))
