"""Порты аутентификации: учётные записи, пароли, токены, коды восстановления, почта."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from core.accounts import Account
from core.mail import MailError as MailFailure

__all__ = [
    "Account",
    "AccountRepository",
    "MailFailure",
    "Mailer",
    "PasswordHasher",
    "ResetCode",
    "ResetCodeHasher",
    "ResetCodeRepository",
    "TokenIssuer",
]


@dataclass(frozen=True, slots=True)
class ResetCode:
    """Действующий код восстановления: только то, что нужно для проверки."""

    id: UUID
    user_id: UUID
    code_hash: str
    attempts: int


class AccountRepository(Protocol):
    async def find_by_email(self, email: str) -> Account | None: ...

    async def get(self, user_id: UUID) -> Account | None: ...

    async def record_login(self, user_id: UUID, at: datetime) -> Account:
        """Отмечает вход и возвращает обновлённую запись."""

    async def set_password(
        self, user_id: UUID, password_hash: str, *, revoke_tokens: bool
    ) -> None:
        """Постоянный пароль: снимает требование смены и срок временного пароля.

        `revoke_tokens` повышает версию токенов, и выданные ранее токены
        перестают приниматься.
        """


class PasswordHasher(Protocol):
    def verify(self, password: str, password_hash: str) -> bool: ...

    def hash(self, password: str) -> str: ...


class TokenIssuer(Protocol):
    def issue(self, user_id: UUID, version: int) -> str: ...


class ResetCodeHasher(Protocol):
    def hash(self, user_id: UUID, code: str) -> str: ...


class ResetCodeRepository(Protocol):
    async def count_since(self, user_id: UUID, since: datetime) -> int:
        """Сколько кодов выдано пользователю позже `since`."""

    async def add(
        self, user_id: UUID, code_hash: str, expires_at: datetime
    ) -> ResetCode: ...

    async def delete(self, code_id: UUID) -> None: ...

    async def latest_active(
        self, user_id: UUID, now: datetime, max_attempts: int
    ) -> ResetCode | None:
        """Последний неиспользованный, неистёкший код с запасом попыток."""

    async def add_failed_attempt(self, code_id: UUID) -> None: ...

    async def invalidate_others(self, user_id: UUID, keep: UUID, at: datetime) -> None:
        """Пометить использованными все активные коды, кроме `keep`."""

    async def consume(self, code: ResetCode, at: datetime) -> None:
        """Пометить использованными `code` и все остальные активные коды."""


class Mailer(Protocol):
    async def send(
        self, to: str, subject: str, text: str, html: str | None = None
    ) -> None:
        """Бросает MailFailure, если письмо не отправлено."""
