"""Сборка зависимостей справочников: порты → SQL-реализации."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.session import get_db
from core.db.unit_of_work import SqlUnitOfWork

from ..app import CatalogService
from ..infra.sql_repo import SqlCatalogRules, SqlDictionaryRepository


def build_catalog_service(db: AsyncSession) -> CatalogService:
    return CatalogService(
        SqlDictionaryRepository(db), SqlCatalogRules(db), SqlUnitOfWork(db)
    )


async def get_catalog_service(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CatalogService:
    return build_catalog_service(db)
