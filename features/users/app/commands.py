"""Команды пользователей: входные данные сценариев без привязки к формату API.

В `UserChanges` поле `provided` отличает «не передано» от «передано как null»;
`fields()` отдаёт только переданные поля (для журнала аудита).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class NewUser:
    email: str
    name: str
    role: str
    access_expires_at: datetime | None = None


@dataclass(frozen=True)
class UserChanges:
    name: str | None = None
    role: str | None = None
    is_active: bool | None = None
    access_expires_at: datetime | None = None
    # True — снять срок доступа (access_expires_at = null).
    access_expires_at_unlimited: bool | None = None
    provided: frozenset[str] = frozenset()

    def fields(self) -> dict:
        return {name: getattr(self, name) for name in self.provided}
