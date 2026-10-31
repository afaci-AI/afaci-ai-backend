"""
Проверка версии мобильного приложения и управление версиями (админ).

  GET    /api/v1/app/version                       — публично, последняя версия (rate-limited)
  POST   /api/v1/admin/app-versions/upload-apk     — загрузить APK и опубликовать версию (админ)
  GET    /api/v1/admin/app-versions                — список всех версий (админ)
  PATCH  /api/v1/admin/app-versions/{id}           — изменить обязательность/описание (админ)
  PATCH  /api/v1/admin/app-versions/{id}/current   — назначить текущей (админ)
  DELETE /api/v1/admin/app-versions/{id}           — удалить версию и APK-файл (админ)

versionName и versionCode берутся из AndroidManifest загружаемого APK; версия
сохраняется, только если её versionCode выше максимального из уже опубликованных.
"""

import os
import re
from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
)
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from pyaxmlparser import APK
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import ClientDisconnect

from api.rate_limit import limiter
from infrastructure.auth import require_admin
from infrastructure.db.models import AppVersion, User
from infrastructure.db.session import get_db

router = APIRouter(tags=["App Version"])

APK_STORAGE_PATH = os.getenv("APK_STORAGE_PATH", "uploads/apk")
APK_BASE_URL = os.getenv("APK_BASE_URL", "/static/apk")
MAX_APK_SIZE = 200 * 1024 * 1024  # 200 МБ


# ----------------------------- схемы -----------------------------
class AppVersionPublic(BaseModel):
    version: str
    versionCode: int
    apkUrl: str
    changelog: str | None = None
    forceUpdate: bool
    minSupportedVersionCode: int | None = None


class AppVersionUpdate(BaseModel):
    changelog: str | None = None
    forceUpdate: bool | None = None
    minSupportedVersionCode: int | None = None


class AppVersionAdmin(BaseModel):
    id: UUID
    version: str
    versionCode: int
    apkUrl: str
    apkFilename: str
    changelog: str | None
    forceUpdate: bool
    minSupportedVersionCode: int | None
    isCurrent: bool
    publishedAt: datetime


# -------------------------- сериализация --------------------------
def _public(v: AppVersion) -> dict:
    return {
        "version": v.version,
        "versionCode": v.version_code,
        "apkUrl": v.apk_url,
        "changelog": v.changelog,
        "forceUpdate": v.force_update,
        "minSupportedVersionCode": v.min_supported_version_code,
    }


def _admin(v: AppVersion) -> dict:
    return {
        "id": v.id,
        "version": v.version,
        "versionCode": v.version_code,
        "apkUrl": v.apk_url,
        "apkFilename": v.apk_filename,
        "changelog": v.changelog,
        "forceUpdate": v.force_update,
        "minSupportedVersionCode": v.min_supported_version_code,
        "isCurrent": v.is_current,
        "publishedAt": v.published_at,
    }


# ----------------------- публичный эндпоинт -----------------------
@router.get("/api/v1/app/version", summary="Текущая версия приложения")
@limiter.limit("30/minute")
async def get_app_version(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    version = (
        await db.execute(
            select(AppVersion).where(AppVersion.is_current.is_(True)).limit(1)
        )
    ).scalar_one_or_none()
    if version is None:
        raise HTTPException(status_code=503, detail="Информация о версии не настроена.")
    return _public(version)


# ------------------------- загрузка APK ---------------------------
def _read_apk_meta(path: str) -> tuple[str, int]:
    """versionName и versionCode из AndroidManifest.xml."""
    try:
        apk = APK(path)
        name = apk.get_androidversion_name()
        code = apk.get_androidversion_code()
        return str(name).strip(), int(code)
    except Exception:
        raise HTTPException(
            status_code=400,
            detail="Не удалось прочитать версию из AndroidManifest.xml этого APK.",
        )


def _remove_quietly(path: str) -> None:
    try:
        os.remove(path)
    except FileNotFoundError:
        pass


@router.post(
    "/api/v1/admin/app-versions/upload-apk",
    status_code=201,
    summary="Загрузить APK и опубликовать версию",
)
async def upload_apk(
    _admin_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    file: Annotated[UploadFile, File()],
    force_update: Annotated[bool, Form(alias="forceUpdate")] = False,
    changelog: Annotated[str | None, Form()] = None,
    min_supported_version_code: Annotated[
        int | None, Form(alias="minSupportedVersionCode", gt=0)
    ] = None,
):
    if not file.filename or not file.filename.lower().endswith(".apk"):
        raise HTTPException(
            status_code=400, detail="Файл должен иметь расширение .apk."
        )

    base = APK_STORAGE_PATH
    os.makedirs(base, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", file.filename)
    filename = f"{timestamp}-{safe_name}"
    path = os.path.join(base, filename)
    # Пока метаданные не проверены, файл лежит под временным именем.
    tmp_path = f"{path}.part"

    size = 0
    magic = b""
    try:
        with open(tmp_path, "wb") as out:  # noqa: ASYNC230 (одноразовая загрузка APK)
            while chunk := await file.read(1024 * 1024):
                if not magic:
                    magic = chunk[:4]
                size += len(chunk)
                if size > MAX_APK_SIZE:
                    out.close()
                    _remove_quietly(tmp_path)
                    raise HTTPException(
                        status_code=413,
                        detail="Файл больше максимального размера (200 МБ).",
                    )
                out.write(chunk)
    except ClientDisconnect:
        _remove_quietly(tmp_path)
        raise HTTPException(
            status_code=400, detail="Соединение прервано, файл не сохранён."
        )

    if size == 0:
        _remove_quietly(tmp_path)
        raise HTTPException(status_code=400, detail="APK-файл пуст.")

    if magic != b"PK\x03\x04":
        _remove_quietly(tmp_path)
        raise HTTPException(
            status_code=400, detail="Файл не является действительным APK архивом."
        )

    try:
        version_name, version_code = await run_in_threadpool(_read_apk_meta, tmp_path)
        if not version_name or version_code <= 0:
            raise HTTPException(
                status_code=400,
                detail="В APK не указаны versionName/versionCode.",
            )
        if (
            min_supported_version_code is not None
            and min_supported_version_code > version_code
        ):
            raise HTTPException(
                status_code=400,
                detail="minSupportedVersionCode не может быть выше versionCode.",
            )

        max_code = (
            await db.execute(select(func.max(AppVersion.version_code)))
        ).scalar_one_or_none()
        if max_code is not None and version_code <= max_code:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"versionCode APK ({version_code}) должен быть выше "
                    f"максимального из опубликованных ({max_code})."
                ),
            )

        os.replace(tmp_path, path)
        await db.execute(
            AppVersion.__table__.update()
            .where(AppVersion.is_current.is_(True))
            .values(is_current=False)
        )
        version = AppVersion(
            version=version_name,
            version_code=version_code,
            apk_url=f"{APK_BASE_URL.rstrip('/')}/{filename}",
            apk_filename=filename,
            changelog=(changelog or "").strip() or None,
            force_update=force_update,
            min_supported_version_code=min_supported_version_code,
            is_current=True,
            published_at=datetime.now(timezone.utc),
        )
        db.add(version)
        await db.commit()
    except IntegrityError:
        await db.rollback()
        _remove_quietly(path)
        raise HTTPException(
            status_code=409, detail="Версия с таким versionCode уже опубликована."
        )
    except BaseException:
        await db.rollback()
        _remove_quietly(tmp_path)
        _remove_quietly(path)
        raise

    await db.refresh(version)
    return _admin(version)


# ------------------------- управление -----------------------------
@router.get("/api/v1/admin/app-versions", summary="Список всех версий")
async def list_app_versions(
    db: Annotated[AsyncSession, Depends(get_db)],
    _admin_user: Annotated[User, Depends(require_admin)],
):
    rows = (
        (await db.execute(select(AppVersion).order_by(AppVersion.version_code.desc())))
        .scalars()
        .all()
    )
    return [_admin(v) for v in rows]


@router.patch("/api/v1/admin/app-versions/{id}", summary="Отредактировать версию")
async def update_app_version(
    id: UUID,
    data: AppVersionUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _admin_user: Annotated[User, Depends(require_admin)],
):
    version = await db.get(AppVersion, id)
    if not version:
        raise HTTPException(status_code=404, detail="Версия не найдена.")

    if data.changelog is not None:
        version.changelog = data.changelog
    if data.forceUpdate is not None:
        version.force_update = data.forceUpdate
    if "minSupportedVersionCode" in data.model_fields_set:
        version.min_supported_version_code = data.minSupportedVersionCode

    await db.commit()
    await db.refresh(version)
    return _admin(version)


@router.patch(
    "/api/v1/admin/app-versions/{id}/current",
    summary="Назначить версию текущей",
)
async def set_current_app_version(
    id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _admin_user: Annotated[User, Depends(require_admin)],
):
    version = await db.get(AppVersion, id)
    if not version:
        raise HTTPException(status_code=404, detail="Версия не найдена.")

    await db.execute(
        AppVersion.__table__.update()
        .where(AppVersion.is_current.is_(True))
        .values(is_current=False)
    )
    version.is_current = True
    await db.commit()
    await db.refresh(version)
    return _admin(version)


@router.delete("/api/v1/admin/app-versions/{id}", summary="Удалить версию")
async def delete_app_version(
    id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _admin_user: Annotated[User, Depends(require_admin)],
):
    version = await db.get(AppVersion, id)
    if not version:
        raise HTTPException(status_code=404, detail="Версия не найдена.")

    was_current = version.is_current
    apk_filename = version.apk_filename
    await db.delete(version)
    await db.flush()

    if was_current:
        # Текущей становится версия с наибольшим versionCode из оставшихся.
        latest = (
            await db.execute(
                select(AppVersion).order_by(AppVersion.version_code.desc()).limit(1)
            )
        ).scalar_one_or_none()
        if latest is not None:
            latest.is_current = True
    await db.commit()

    if not apk_filename.startswith(("http://", "https://")):
        _remove_quietly(os.path.join(APK_STORAGE_PATH, os.path.basename(apk_filename)))
    return {"status": "deleted"}
