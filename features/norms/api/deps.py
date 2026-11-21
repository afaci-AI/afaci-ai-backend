"""Сборка зависимостей норм: порт → SQL-реализация (composition root)."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.session import get_db

from ..app import NormsService
from ..infra.sql_repo import SqlNormsRepository


async def get_norms_service(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> NormsService:
    return NormsService(SqlNormsRepository(db))
