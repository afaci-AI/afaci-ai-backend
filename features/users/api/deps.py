"""Сборка зависимостей пользователей."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.session import get_db
from core.db.unit_of_work import SqlUnitOfWork
from core.mail import SmtpMailer

from ..app import UserService
from ..infra.sql_repo import BcryptHasher, SqlUserRepository, UserChangeAudit


async def get_user_service(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserService:
    return UserService(
        SqlUserRepository(db),
        SqlUnitOfWork(db),
        BcryptHasher(),
        UserChangeAudit(),
        SmtpMailer(),
    )
