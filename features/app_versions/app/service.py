"""Сценарии версий мобильного приложения: публикация, загрузка APK, управление."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

from core.errors import (
    AppError,
    BadRequestError,
    NotFoundError,
    PayloadTooLargeError,
    ServiceUnavailableError,
)

from ..domain.apk import APK_MAGIC, ApkError, has_apk_extension, public_apk_url
from .commands import AppVersionChanges, NewAppVersion
from .ports import (
    ApkInspector,
    ApkStorage,
    AppVersionRepository,
    AppVersionRow,
    ReadChunk,
)

NOT_FOUND = "Версия не найдена."


def _error(exc: ApkError) -> AppError:
    kinds = {413: PayloadTooLargeError, 503: ServiceUnavailableError}
    return kinds.get(exc.status, BadRequestError)(exc.detail)


class AppVersionService:
    def __init__(
        self,
        repo: AppVersionRepository,
        storage: ApkStorage,
        inspector: ApkInspector,
        apk_base_url: str,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._repo = repo
        self._storage = storage
        self._inspector = inspector
        self._base_url = apk_base_url
        self._now = now

    async def _get(self, version_id: UUID) -> AppVersionRow:
        version = await self._repo.get(version_id)
        if not version:
            raise NotFoundError(NOT_FOUND)
        return version

    async def current(self) -> AppVersionRow:
        version = await self._repo.current()
        if version is None:
            raise ServiceUnavailableError("Информация о версии не настроена.")
        return version

    async def list(self) -> list[AppVersionRow]:
        return await self._repo.list()

    async def create(self, command: NewAppVersion) -> AppVersionRow:
        """Публикует версию (APK уже в хранилище либо внешняя ссылка)."""
        await self._repo.lock_publication()
        await self._check_version_code(command.version_code)
        self._check_apk_exists(command.apk_filename)
        return await self._publish(command)

    async def _check_version_code(self, version_code: int) -> None:
        max_code = await self._repo.max_version_code()
        if max_code is not None and version_code <= max_code:
            raise BadRequestError(
                f"versionCode должен быть больше текущего максимального значения ({max_code})."
            )

    def _check_apk_exists(self, filename: str) -> None:
        if filename.startswith(("http://", "https://")):
            return
        if not self._storage.exists(filename.lstrip("/")):
            raise BadRequestError(
                "Указанный APK-файл не найден в хранилище. Сначала загрузите файл."
            )

    async def _publish(self, command: NewAppVersion) -> AppVersionRow:
        if command.is_current:
            await self._repo.clear_current()
        return await self._repo.add(
            {
                "version": command.version,
                "version_code": command.version_code,
                "apk_url": public_apk_url(self._base_url, command.apk_filename),
                "apk_filename": command.apk_filename,
                "changelog": command.changelog,
                "force_update": command.force_update,
                "min_supported_version_code": command.min_supported_version_code,
                "is_current": command.is_current,
                "published_at": self._now(),
            }
        )

    async def upload(
        self,
        *,
        original_name: str | None,
        read_chunk: ReadChunk,
        force_update: bool,
        changelog: str | None,
        min_supported_version_code: int | None,
    ) -> AppVersionRow:
        if not has_apk_extension(original_name):
            raise BadRequestError("Файл должен иметь расширение .apk.")

        try:
            stored = await self._storage.store(original_name, read_chunk)
        except ApkError as exc:
            raise _error(exc) from exc

        if stored.size == 0:
            self._storage.remove(stored.path)
            raise BadRequestError("APK-файл пуст.")
        if stored.magic != APK_MAGIC:
            self._storage.remove(stored.path)
            raise BadRequestError("Файл не является действительным APK архивом.")

        try:
            version, version_code = await asyncio.to_thread(
                self._inspector.read_version, stored.path
            )
            return await self.create(
                NewAppVersion(
                    version=version,
                    version_code=version_code,
                    apk_filename=stored.filename,
                    changelog=changelog,
                    force_update=force_update,
                    min_supported_version_code=min_supported_version_code,
                )
            )
        except BaseException as exc:
            await self._repo.rollback()
            self._storage.remove(stored.path)
            if isinstance(exc, ApkError):
                raise _error(exc) from exc
            raise

    async def update(
        self, version_id: UUID, changes: AppVersionChanges
    ) -> AppVersionRow:
        version = await self._get(version_id)
        if changes.version is not None:
            version.version = changes.version
        if changes.changelog is not None:
            version.changelog = changes.changelog
        if changes.force_update is not None:
            version.force_update = changes.force_update
        if "min_supported_version_code" in changes.provided:
            version.min_supported_version_code = changes.min_supported_version_code
        return await self._repo.save(version)

    async def set_current(self, version_id: UUID) -> AppVersionRow:
        version = await self._get(version_id)
        await self._repo.clear_current()
        version.is_current = True
        return await self._repo.save(version)

    async def delete(self, version_id: UUID) -> dict:
        version = await self._get(version_id)
        if version.is_current:
            raise BadRequestError("Нельзя удалить текущую версию.")
        await self._repo.delete(version)
        return {"status": "deleted"}
