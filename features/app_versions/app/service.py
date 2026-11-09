"""Сценарии версий мобильного приложения: публикация, загрузка APK, управление."""

from __future__ import annotations

import asyncio
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
from .ports import (
    ApkInspector,
    ApkStorage,
    AppVersionRepository,
    ReadChunk,
    Row,
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
    ) -> None:
        self._repo = repo
        self._storage = storage
        self._inspector = inspector
        self._base_url = apk_base_url

    async def _get(self, version_id: UUID) -> Row:
        version = await self._repo.get(version_id)
        if not version:
            raise NotFoundError(NOT_FOUND)
        return version

    async def current(self) -> Row:
        version = await self._repo.current()
        if version is None:
            raise ServiceUnavailableError("Информация о версии не настроена.")
        return version

    async def list(self) -> list[Row]:
        return await self._repo.list()

    async def create(self, data: dict) -> Row:
        """Публикует версию (APK уже в хранилище либо внешняя ссылка)."""
        await self._repo.lock_publication()
        max_code = await self._repo.max_version_code()
        if max_code is not None and data["versionCode"] <= max_code:
            raise BadRequestError(
                f"versionCode должен быть больше текущего максимального значения ({max_code})."
            )

        filename = data["apkFilename"]
        is_external = filename.startswith(("http://", "https://"))
        if not is_external and not self._storage.exists(filename.lstrip("/")):
            raise BadRequestError(
                "Указанный APK-файл не найден в хранилище. Сначала загрузите файл."
            )

        if data["isCurrent"]:
            await self._repo.clear_current()

        return await self._repo.add(
            {
                "version": data["version"],
                "version_code": data["versionCode"],
                "apk_url": public_apk_url(self._base_url, filename),
                "apk_filename": filename,
                "changelog": data["changelog"],
                "force_update": data["forceUpdate"],
                "min_supported_version_code": data["minSupportedVersionCode"],
                "is_current": data["isCurrent"],
                "published_at": datetime.now(UTC),
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
    ) -> Row:
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
                {
                    "version": version,
                    "versionCode": version_code,
                    "apkFilename": stored.filename,
                    "changelog": changelog,
                    "forceUpdate": force_update,
                    "minSupportedVersionCode": min_supported_version_code,
                    "isCurrent": True,
                }
            )
        except BaseException as exc:
            await self._repo.rollback()
            self._storage.remove(stored.path)
            if isinstance(exc, ApkError):
                raise _error(exc) from exc
            raise

    async def update(self, version_id: UUID, changes: dict) -> Row:
        """changes — поля запроса, переданные клиентом (exclude_unset)."""
        version = await self._get(version_id)
        if changes.get("version") is not None:
            version.version = changes["version"]
        if changes.get("changelog") is not None:
            version.changelog = changes["changelog"]
        if changes.get("forceUpdate") is not None:
            version.force_update = changes["forceUpdate"]
        if "minSupportedVersionCode" in changes:
            version.min_supported_version_code = changes["minSupportedVersionCode"]
        return await self._repo.save(version)

    async def set_current(self, version_id: UUID) -> Row:
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
