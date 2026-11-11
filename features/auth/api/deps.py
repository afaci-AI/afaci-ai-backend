"""Сборка зависимостей аутентификации."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.session import get_db

from ..app import AuthService
from ..infra.security_adapter import SecurityCredentials, SqlAccountRepository


async def get_auth_service(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AuthService:
    return AuthService(SqlAccountRepository(db), SecurityCredentials())
