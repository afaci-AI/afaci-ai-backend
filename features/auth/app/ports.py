"""Порты аутентификации: поиск и сохранение пользователя, пароли и токены."""

from __future__ import annotations

from typing import Any, Protocol

Row = Any


class AccountRepository(Protocol):
    async def find_by_email(self, email: str) -> Row | None: ...

    async def save(self, row: Row) -> Row:
        """Сохраняет изменения и обновляет запись."""


class Credentials(Protocol):
    def verify_password(self, password: str, password_hash: str) -> bool: ...

    def hash_password(self, password: str) -> str: ...

    def issue_token(self, user_id) -> str: ...

    def is_expired(self, user: Row) -> bool: ...
