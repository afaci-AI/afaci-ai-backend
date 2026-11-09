"""Порты версий приложения: хранилище записей, файлов и чтение версии из APK."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID

Row = Any
ReadChunk = Callable[[int], Awaitable[bytes]]


@dataclass
class StoredApk:
    filename: str
    path: str
    size: int
    magic: bytes


class AppVersionRepository(Protocol):
    async def current(self) -> Row | None: ...

    async def list(self) -> list[Row]:
        """Все версии по убыванию versionCode."""

    async def get(self, version_id: UUID) -> Row | None: ...

    async def lock_publication(self) -> None:
        """Сериализует публикации, в том числе параллельные загрузки."""

    async def max_version_code(self) -> int | None: ...

    async def clear_current(self) -> None: ...

    async def add(self, data: dict) -> Row: ...

    async def save(self, row: Row) -> Row: ...

    async def delete(self, row: Row) -> None: ...

    async def rollback(self) -> None: ...


class ApkStorage(Protocol):
    def exists(self, filename: str) -> bool: ...

    async def store(self, original_name: str, read_chunk: ReadChunk) -> StoredApk:
        """Потоком сохраняет файл. ApkError — слишком большой или обрыв связи."""

    def remove(self, path: str) -> None: ...


class ApkInspector(Protocol):
    def read_version(self, path: str) -> tuple[str, int]:
        """(versionName, versionCode) из APK. Блокирующий вызов."""
