"""SQL-хранилище учётных записей и адаптеры хеширования и токенов поверх core.security."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core import security
from core.accounts import Account
from core.db.models import User


class SqlAccountRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def _row(self, user_id: UUID) -> User:
        row = await self._db.get(User, user_id)
        if row is None:
            raise LookupError(f"Нет пользователя {user_id}")
        return row

    async def find_by_email(self, email: str) -> Account | None:
        res = await self._db.execute(select(User).where(User.email == email))
        row = res.scalar_one_or_none()
        return Account.of(row) if row is not None else None

    async def get(self, user_id: UUID) -> Account | None:
        row = await self._db.get(User, user_id)
        return Account.of(row) if row is not None else None

    async def record_login(self, user_id: UUID, at: datetime) -> Account:
        row = await self._row(user_id)
        row.last_login_at = at
        await self._db.commit()
        await self._db.refresh(row)
        return Account.of(row)

    async def set_password(
        self, user_id: UUID, password_hash: str, *, revoke_tokens: bool
    ) -> None:
        row = await self._row(user_id)
        row.password_hash = password_hash
        row.must_change_password = False
        row.temp_password_expires_at = None
        if revoke_tokens:
            row.token_version = (row.token_version or 0) + 1
        await self._db.commit()


class BcryptPasswords:
    def verify(self, password: str, password_hash: str) -> bool:
        return security.verify_password(password, password_hash)

    def hash(self, password: str) -> str:
        return security.hash_password(password)


class JwtTokens:
    def issue(self, user_id: UUID, version: int) -> str:
        return security.create_access_token(user_id, version)


class HmacResetCodes:
    def hash(self, user_id: UUID, code: str) -> str:
        return security.hash_reset_code(user_id, code)
