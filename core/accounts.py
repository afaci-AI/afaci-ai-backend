"""Учётная запись пользователя как данные: граница портов auth и users.

Сервисы получают из хранилища неизменяемую `Account`, а изменения передают
отдельными операциями порта: объект ORM за пределы `infra` не выходит.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

__all__ = ["Account", "access_expired"]


def access_expired(access_expires_at: datetime | None, now: datetime) -> bool:
    """`access_expires_at = None` значит безлимитный доступ."""
    return access_expires_at is not None and access_expires_at <= now


@dataclass(frozen=True, slots=True)
class Account:
    id: UUID
    email: str
    name: str
    role: str
    password_hash: str
    is_active: bool
    access_expires_at: datetime | None
    must_change_password: bool
    temp_password_expires_at: datetime | None
    token_version: int
    created_at: datetime | None
    last_login_at: datetime | None

    @classmethod
    def of(cls, row) -> Account:
        """Снимок записи хранилища с теми же именами полей."""
        return cls(
            id=row.id,
            email=row.email,
            name=row.name,
            role=row.role,
            password_hash=row.password_hash,
            is_active=row.is_active,
            access_expires_at=row.access_expires_at,
            must_change_password=row.must_change_password,
            temp_password_expires_at=row.temp_password_expires_at,
            token_version=row.token_version or 0,
            created_at=row.created_at,
            last_login_at=row.last_login_at,
        )

    def access_expired(self, now: datetime) -> bool:
        return access_expired(self.access_expires_at, now)
