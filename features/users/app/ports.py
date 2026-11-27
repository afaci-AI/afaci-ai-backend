"""Порты управления пользователями: хранилище отдаёт и принимает данные, не ORM."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from core.accounts import Account
from core.mail import MailError as MailFailure

__all__ = [
    "Account",
    "AccountEdit",
    "ChangeAudit",
    "MailFailure",
    "Mailer",
    "NewAccount",
    "PasswordHasher",
    "UnitOfWork",
    "UserRepository",
]


@dataclass(frozen=True, slots=True)
class NewAccount:
    email: str
    name: str
    password_hash: str
    role: str
    access_expires_at: datetime | None
    temp_password_expires_at: datetime


@dataclass(frozen=True, slots=True)
class AccountEdit:
    """Поля, которые меняет администратор; значения — итоговые, не дельта."""

    role: str
    is_active: bool
    name: str
    access_expires_at: datetime | None

    @classmethod
    def of(cls, user: Account) -> AccountEdit:
        return cls(
            role=user.role,
            is_active=user.is_active,
            name=user.name,
            access_expires_at=user.access_expires_at,
        )


class UnitOfWork(Protocol):
    """Транзакция сценария: единственное место фиксации и отката."""

    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...


class UserRepository(Protocol):
    """Изменения только готовятся: фиксирует их `UnitOfWork`."""

    async def list(
        self, *, role: str | None = None, search: str | None = None
    ) -> list[Account]:
        """Пользователи по убыванию даты создания.

        `role` — только этой роли; `search` — email или имя содержат запрос без
        учёта регистра (включая кириллицу), `ё/е`, пробелов и дефисов.
        """

    async def get(self, user_id: UUID) -> Account | None: ...

    async def find_by_email(self, email: str) -> Account | None: ...

    async def add(self, new: NewAccount) -> Account:
        """Новая запись с временным паролем, который нужно сменить при входе."""

    async def update(self, user_id: UUID, edit: AccountEdit) -> Account: ...

    async def set_temp_password(
        self, user_id: UUID, password_hash: str, expires_at: datetime
    ) -> Account:
        """Новый временный пароль; сессии со старым паролем завершаются."""


class PasswordHasher(Protocol):
    def hash(self, password: str) -> str: ...


class ChangeAudit(Protocol):
    def user_updated(
        self, admin_id: UUID, user: Account, user_id: UUID, changes: dict
    ) -> None: ...


class Mailer(Protocol):
    async def send(
        self, to: str, subject: str, text: str, html: str | None = None
    ) -> None:
        """Бросает MailFailure, если письмо не отправлено."""
