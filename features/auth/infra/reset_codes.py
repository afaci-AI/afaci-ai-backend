"""SQL-хранилище кодов восстановления пароля."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.models import PasswordResetCode

from ..app.ports import Row


class SqlResetCodeRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def count_since(self, user_id: UUID, since: datetime) -> int:
        query = select(func.count()).where(
            PasswordResetCode.user_id == user_id,
            PasswordResetCode.created_at > since,
        )
        return int((await self._db.execute(query)).scalar_one())

    async def add(self, user_id: UUID, code_hash: str, expires_at: datetime) -> Row:
        row = PasswordResetCode(
            user_id=user_id, code_hash=code_hash, expires_at=expires_at, attempts=0
        )
        self._db.add(row)
        await self._db.commit()
        await self._db.refresh(row)
        return row

    async def delete(self, row: Row) -> None:
        await self._db.delete(row)
        await self._db.commit()

    async def latest_active(
        self, user_id: UUID, now: datetime, max_attempts: int
    ) -> Row | None:
        query = (
            select(PasswordResetCode)
            .where(
                PasswordResetCode.user_id == user_id,
                PasswordResetCode.used_at.is_(None),
                PasswordResetCode.expires_at > now,
                PasswordResetCode.attempts < max_attempts,
            )
            .order_by(PasswordResetCode.created_at.desc())
            .limit(1)
        )
        return (await self._db.execute(query)).scalar_one_or_none()

    async def invalidate_others(self, user_id: UUID, keep: UUID, at: datetime) -> None:
        await self._db.execute(
            update(PasswordResetCode)
            .where(
                PasswordResetCode.user_id == user_id,
                PasswordResetCode.id != keep,
                PasswordResetCode.used_at.is_(None),
            )
            .values(used_at=at)
        )
        await self._db.commit()

    async def save(self, row: Row) -> Row:
        await self._db.commit()
        await self._db.refresh(row)
        return row
