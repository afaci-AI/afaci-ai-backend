"""SQL-реализация хранилища пользователей и адаптеры хеширования и аудита."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.audit import log_audit_change
from core.db.models import User
from core.security import hash_password

from ..app.ports import Row


class SqlUserRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def list(self, role: str | None) -> list[Row]:
        query = select(User)
        if role:
            query = query.where(User.role == role)
        res = await self._db.execute(query.order_by(User.created_at.desc()))
        return list(res.scalars().all())

    async def get(self, user_id: UUID) -> Row | None:
        return await self._db.get(User, user_id)

    async def find_by_email(self, email: str) -> Row | None:
        res = await self._db.execute(select(User).where(User.email == email))
        return res.scalar_one_or_none()

    async def add(self, data: dict) -> Row:
        user = User(**data)
        self._db.add(user)
        await self._db.commit()
        await self._db.refresh(user)
        return user

    async def save(self, row: Row) -> Row:
        await self._db.commit()
        await self._db.refresh(row)
        return row


class BcryptHasher:
    def hash(self, password: str) -> str:
        return hash_password(password)


class UserChangeAudit:
    def user_updated(
        self, admin_id: UUID, user: Row, user_id: UUID, changes: dict
    ) -> None:
        # Аудит мутации (ТЗ п.4): фиксируем кто и что изменил
        log_audit_change(
            action="update_user",
            target_type="User",
            target_id=str(user_id),
            changed_fields=changes,
            actor=str(admin_id),
            extra={"target_email": user.email},
        )
