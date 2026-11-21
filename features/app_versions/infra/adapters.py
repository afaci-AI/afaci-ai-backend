"""Реализации портов версий: SQL-хранилище, файловое хранилище APK и чтение через aapt."""

from __future__ import annotations

import os
import subprocess
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import ClientDisconnect

from core.db.models import AppVersion

from ..app.ports import ReadChunk, Row, StoredApk
from ..domain.apk import MAX_APK_SIZE, ApkError, parse_badging, stored_filename

PUBLICATION_LOCK = 86422107


class SqlAppVersionRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def current(self) -> Row | None:
        return (
            await self._db.execute(
                select(AppVersion).where(AppVersion.is_current.is_(True)).limit(1)
            )
        ).scalar_one_or_none()

    async def list(self) -> list[Row]:
        rows = (
            await self._db.execute(
                select(AppVersion).order_by(AppVersion.version_code.desc())
            )
        ).scalars()
        return list(rows.all())

    async def get(self, version_id: UUID) -> Row | None:
        return await self._db.get(AppVersion, version_id)

    async def lock_publication(self) -> None:
        await self._db.execute(
            text(f"SELECT pg_advisory_xact_lock({PUBLICATION_LOCK})")
        )

    async def max_version_code(self) -> int | None:
        return (
            await self._db.execute(select(func.max(AppVersion.version_code)))
        ).scalar_one_or_none()

    async def clear_current(self) -> None:
        await self._db.execute(
            AppVersion.__table__.update()
            .where(AppVersion.is_current.is_(True))
            .values(is_current=False)
        )

    async def add(self, data: dict) -> Row:
        version = AppVersion(**data)
        self._db.add(version)
        await self._db.commit()
        await self._db.refresh(version)
        return version

    async def save(self, row: Row) -> Row:
        await self._db.commit()
        await self._db.refresh(row)
        return row

    async def delete(self, row: Row) -> None:
        await self._db.delete(row)
        await self._db.commit()

    async def rollback(self) -> None:
        await self._db.rollback()


class FileApkStorage:
    def __init__(self, base_path: str) -> None:
        self._base = base_path

    def exists(self, filename: str) -> bool:
        return os.path.isfile(os.path.join(self._base, filename))

    async def store(self, original_name: str, read_chunk: ReadChunk) -> StoredApk:
        from datetime import UTC, datetime
        from uuid import uuid4

        os.makedirs(self._base, exist_ok=True)
        timestamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
        filename = stored_filename(original_name, timestamp, uuid4().hex)
        path = os.path.join(self._base, filename)

        size = 0
        magic = b""
        try:
            with open(path, "wb") as out:  # noqa: ASYNC230 (одноразовая загрузка APK)
                while chunk := await read_chunk(1024 * 1024):
                    if not magic:
                        magic = chunk[:4]
                    size += len(chunk)
                    if size > MAX_APK_SIZE:
                        out.close()
                        os.remove(path)
                        raise ApkError(
                            "Файл больше максимального размера (200 МБ).", 413
                        )
                    out.write(chunk)
        except ClientDisconnect as exc:
            if os.path.exists(path):
                os.remove(path)
            raise ApkError("Соединение прервано, файл не сохранён.") from exc
        return StoredApk(filename=filename, path=path, size=size, magic=magic)

    def remove(self, path: str) -> None:
        if os.path.exists(path):
            os.remove(path)


class AaptInspector:
    """Читает скомпилированный манифест инструментом упаковки Android."""

    def read_version(self, path: str) -> tuple[str, int]:
        try:
            result = subprocess.run(
                [os.getenv("AAPT_PATH", "aapt"), "dump", "badging", path],
                capture_output=True,
                text=True,
                timeout=30,
                check=True,
            )
        except FileNotFoundError as exc:
            raise ApkError("На сервере не настроено чтение APK (aapt).", 503) from exc
        except (subprocess.SubprocessError, UnicodeError) as exc:
            raise ApkError("Не удалось прочитать AndroidManifest.xml из APK.") from exc
        return parse_badging(result.stdout)
