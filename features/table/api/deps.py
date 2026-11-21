"""Сборка зависимостей таблиц: порт → SQL-реализация."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.session import get_db

from ..app import TableService
from ..infra.sql_queries import SqlTableQueries


async def get_table_service(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TableService:
    return TableService(SqlTableQueries(db))
