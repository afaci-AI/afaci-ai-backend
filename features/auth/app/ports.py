"""Порты аутентификации: пользователи, пароли, токены, коды восстановления, почта."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from core.mail import MailError as MailFailure

Row = Any

__all__ = [
    "AccountRepository",
    "Credentials",
    "MailFailure",
    "Mailer",
    "ResetCodeRepository",
    "Row",
]


class AccountRepository(Protocol):
    async def find_by_email(self, email: str) -> Row | None: ...

    async def save(self, row: Row) -> Row:
        """Сохраняет изменения и обновляет запись."""


class Credentials(Protocol):
    def verify_password(self, password: str, password_hash: str) -> bool: ...

    def hash_password(self, password: str) -> str: ...

    def hash_reset_code(self, user_id: UUID, code: str) -> str: ...

    def issue_token(self, user: Row) -> str: ...

    def is_expired(self, user: Row) -> bool: ...


class ResetCodeRepository(Protocol):
    async def count_since(self, user_id: UUID, since: datetime) -> int:
        """Сколько кодов выдано пользователю позже `since`."""

    async def add(self, user_id: UUID, code_hash: str, expires_at: datetime) -> Row: ...

    async def delete(self, row: Row) -> None: ...

    async def latest_active(
        self, user_id: UUID, now: datetime, max_attempts: int
    ) -> Row | None:
        """Последний неиспользованный, неистёкший код с запасом попыток."""

    async def invalidate_others(self, user_id: UUID, keep: UUID, at: datetime) -> None:
        """Пометить использованными все активные коды, кроме `keep`."""

    async def save(self, row: Row) -> Row: ...


class Mailer(Protocol):
    async def send(
        self, to: str, subject: str, text: str, html: str | None = None
    ) -> None:
        """Бросает MailFailure, если письмо не отправлено."""
