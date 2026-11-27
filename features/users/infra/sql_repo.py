"""SQL-реализация хранилища пользователей и адаптеры хеширования и аудита."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from core.accounts import Account
from core.audit import log_audit_change
from core.db.models import User
from core.db.text_filters import contains_clause
from core.security import hash_password

from ..app.ports import AccountEdit, NewAccount


class SqlUserRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def _row(self, user_id: UUID) -> User:
        row = await self._db.get(User, user_id)
        if row is None:
            raise LookupError(f"Нет пользователя {user_id}")
        return row

    async def _saved(self, row: User) -> Account:
        await self._db.commit()
        await self._db.refresh(row)
        return Account.of(row)

    async def list(
        self, *, role: str | None = None, search: str | None = None
    ) -> list[Account]:
        query = select(User)
        if role:
            query = query.where(User.role == role)
        if search:
            query = query.where(_search_clause(search))
        res = await self._db.execute(query.order_by(User.created_at.desc()))
        return [Account.of(row) for row in res.scalars().all()]

    async def get(self, user_id: UUID) -> Account | None:
        row = await self._db.get(User, user_id)
        return Account.of(row) if row is not None else None

    async def find_by_email(self, email: str) -> Account | None:
        res = await self._db.execute(select(User).where(User.email == email))
        row = res.scalar_one_or_none()
        return Account.of(row) if row is not None else None

    async def add(self, new: NewAccount) -> Account:
        row = User(
            email=new.email,
            name=new.name,
            password_hash=new.password_hash,
            role=new.role,
            access_expires_at=new.access_expires_at,
            must_change_password=True,
            temp_password_expires_at=new.temp_password_expires_at,
        )
        self._db.add(row)
        return await self._saved(row)

    async def update(self, user_id: UUID, edit: AccountEdit) -> Account:
        row = await self._row(user_id)
        row.role = edit.role
        row.is_active = edit.is_active
        row.name = edit.name
        row.access_expires_at = edit.access_expires_at
        return await self._saved(row)

    async def set_temp_password(
        self, user_id: UUID, password_hash: str, expires_at: datetime
    ) -> Account:
        row = await self._row(user_id)
        row.password_hash = password_hash
        row.temp_password_expires_at = expires_at
        row.token_version = (row.token_version or 0) + 1
        return await self._saved(row)


def _search_clause(search: str):
    """Email или имя содержат запрос. `ILIKE` не годится: БД в локали C не
    сворачивает регистр кириллицы, поэтому нормализация — `text_filters`."""
    by_email, email_params = contains_clause("users.email", search, "ue")
    by_name, name_params = contains_clause("users.name", search, "un")
    if not by_email:
        return text("TRUE")
    return text(f"({by_email} OR {by_name})").bindparams(**email_params, **name_params)


class BcryptHasher:
    def hash(self, password: str) -> str:
        return hash_password(password)


class UserChangeAudit:
    def user_updated(
        self, admin_id: UUID, user: Account, user_id: UUID, changes: dict
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
