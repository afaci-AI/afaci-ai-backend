"""Порты управления пользователями. Запись пользователя — объект хранилища."""

from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID

Row = Any


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
