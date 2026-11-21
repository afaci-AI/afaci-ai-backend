"""Сборка зависимостей аутентификации."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.session import get_db
from core.mail import SmtpMailer

from ..app import AuthService, PasswordResetService
from ..infra.reset_codes import SqlResetCodeRepository
from ..infra.security_adapter import SecurityCredentials, SqlAccountRepository


async def get_auth_service(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AuthService:
    return AuthService(SqlAccountRepository(db), SecurityCredentials())


async def get_password_reset_service(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PasswordResetService:
    return PasswordResetService(
        SqlAccountRepository(db),
        SqlResetCodeRepository(db),
        SecurityCredentials(),
        SmtpMailer(),
    )
