"""Порты версий приложения: хранилище записей, файлов и чтение версии из APK."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

ReadChunk = Callable[[int], Awaitable[bytes]]


class AppVersionRow(Protocol):
    """Запись версии в хранилище (ORM); поля, которые читают и меняют сценарии."""

    id: UUID
    version: str
    version_code: int
    changelog: str | None
    force_update: bool
    min_supported_version_code: int | None
    is_current: bool


@dataclass(frozen=True)
class NewVersionRecord:
    """Поля новой записи версии; публичный адрес и время уже вычислены."""

    version: str
    version_code: int
    apk_url: str
    apk_filename: str
    changelog: str | None
    force_update: bool
    min_supported_version_code: int | None
    is_current: bool
    published_at: datetime


@dataclass
class StoredApk:
    filename: str
    path: str
    size: int
    magic: bytes


class AppVersionRepository(Protocol):
    """Изменения только готовятся: фиксирует и откатывает их `UnitOfWork`."""

    async def current(self) -> AppVersionRow | None: ...

    async def list(self) -> list[AppVersionRow]:
        """Все версии по убыванию versionCode."""

    async def get(self, version_id: UUID) -> AppVersionRow | None: ...

    async def lock_publication(self) -> None:
        """Сериализует публикации, в том числе параллельные загрузки."""

    async def max_version_code(self) -> int | None: ...

    async def clear_current(self) -> None: ...

    async def add(self, record: NewVersionRecord) -> AppVersionRow: ...

    async def save(self, row: AppVersionRow) -> AppVersionRow: ...

    async def delete(self, row: AppVersionRow) -> None: ...


class UnitOfWork(Protocol):
    """Транзакция сценария: единственное место фиксации и отката."""

    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...

    async def refresh(self, row: object) -> None:
        """Перечитывает значения, выставленные базой при фиксации."""


class ApkStorage(Protocol):
    def exists(self, filename: str) -> bool: ...

    async def store(self, original_name: str, read_chunk: ReadChunk) -> StoredApk:
        """Потоком сохраняет файл. ApkError — слишком большой или обрыв связи."""

    def remove(self, path: str) -> None: ...


class ApkInspector(Protocol):
    def read_version(self, path: str) -> tuple[str, int]:
        """(versionName, versionCode) из APK. Блокирующий вызов."""
