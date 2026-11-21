"""SQL-хранилище учётных записей и адаптер хеширования/токенов поверх core.security."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core import security
from core.db.models import User

from ..app.ports import Row


class SqlAccountRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def find_by_email(self, email: str) -> Row | None:
        res = await self._db.execute(select(User).where(User.email == email))
        return res.scalar_one_or_none()

    async def save(self, row: Row) -> Row:
        await self._db.commit()
        await self._db.refresh(row)
        return row


class SecurityCredentials:
    def verify_password(self, password: str, password_hash: str) -> bool:
        return security.verify_password(password, password_hash)

    def hash_password(self, password: str) -> str:
        return security.hash_password(password)

    def issue_token(self, user_id) -> str:
        return security.create_access_token(user_id)

    def is_expired(self, user: Row) -> bool:
        return security.is_expired(user)
