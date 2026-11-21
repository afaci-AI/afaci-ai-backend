"""Порты управления пользователями. Запись пользователя — объект хранилища."""

from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID

from core.mail import MailError as MailFailure

Row = Any

__all__ = [
    "ChangeAudit",
    "MailFailure",
    "Mailer",
    "PasswordHasher",
    "Row",
    "UserRepository",
]


class UserRepository(Protocol):
    async def list(self, role: str | None) -> list[Row]:
        """Пользователи по убыванию даты создания, при `role` — только этой роли."""

    async def get(self, user_id: UUID) -> Row | None: ...

    async def find_by_email(self, email: str) -> Row | None: ...

    async def add(self, data: dict) -> Row: ...

    async def save(self, row: Row) -> Row: ...


class PasswordHasher(Protocol):
    def hash(self, password: str) -> str: ...


class ChangeAudit(Protocol):
    def user_updated(
        self, admin_id: UUID, user: Row, user_id: UUID, changes: dict
    ) -> None: ...


class Mailer(Protocol):
    async def send(
        self, to: str, subject: str, text: str, html: str | None = None
    ) -> None:
        """Бросает MailFailure, если письмо не отправлено."""
