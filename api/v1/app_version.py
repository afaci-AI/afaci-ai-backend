"""
Проверка версии мобильного приложения и управление версиями (админ).

  GET    /api/v1/app/version                       — публично, текущая версия (rate-limited)
  POST   /api/v1/admin/app-versions/upload-apk     — загрузить APK файл (админ)
  GET    /api/v1/admin/app-versions                — список всех версий (админ)
  POST   /api/v1/admin/app-versions                — создать версию (админ)
  PATCH  /api/v1/admin/app-versions/{id}           — отредактировать версию (админ)
  PATCH  /api/v1/admin/app-versions/{id}/current   — назначить текущей (админ)
  DELETE /api/v1/admin/app-versions/{id}           — удалить версию (админ)
"""

import os
import re
from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

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


class AppVersionCreate(BaseModel):
    version: str = Field(min_length=1)
    versionCode: int = Field(gt=0)
    apkFilename: str = Field(min_length=1)
    changelog: str | None = None
    forceUpdate: bool = False
    minSupportedVersionCode: int | None = None
    isCurrent: bool = True


class AppVersionUpdate(BaseModel):
    version: str | None = None
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


class UploadApkResponse(BaseModel):
    filename: str
    url: str


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
        raise HTTPException(
            status_code=503, detail="Информация о версии не настроена."
        )
    return _public(version)


# ------------------------- загрузка APK ---------------------------
@router.post(
    "/api/v1/admin/app-versions/upload-apk",
    status_code=201,
    summary="Загрузить APK файл",
)
async def upload_apk(
    _admin_user: Annotated[User, Depends(require_admin)],
    file: Annotated[UploadFile, File()],
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

    size = 0
    with open(path, "wb") as out:  # noqa: ASYNC230 (одноразовая загрузка APK)
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_APK_SIZE:
                out.close()
                os.remove(path)
                raise HTTPException(
                    status_code=413, detail="Файл больше максимального размера (200 МБ)."
                )
            out.write(chunk)

    url = f"{APK_BASE_URL.rstrip('/')}/{filename}"
    return UploadApkResponse(filename=filename, url=url)


# ------------------------- управление -----------------------------
@router.get("/api/v1/admin/app-versions", summary="Список всех версий")
async def list_app_versions(
    db: Annotated[AsyncSession, Depends(get_db)],
    _admin_user: Annotated[User, Depends(require_admin)],
):
    rows = (
        await db.execute(
            select(AppVersion).order_by(AppVersion.version_code.desc())
        )
    ).scalars().all()
    return [_admin(v) for v in rows]


@router.post(
    "/api/v1/admin/app-versions", status_code=201, summary="Создать версию"
)
async def create_app_version(
    data: AppVersionCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _admin_user: Annotated[User, Depends(require_admin)],
):
    max_code = (
        await db.execute(select(func.max(AppVersion.version_code)))
    ).scalar_one_or_none()
    if max_code is not None and data.versionCode <= max_code:
        raise HTTPException(
            status_code=400,
            detail=f"versionCode должен быть больше текущего максимального значения ({max_code}).",
        )

    apk_url = (
        f"{APK_BASE_URL.rstrip('/')}/{data.apkFilename.lstrip('/')}"
        if not data.apkFilename.startswith(("http://", "https://"))
        else data.apkFilename
    )

    if data.isCurrent:
        await db.execute(
            AppVersion.__table__.update()
            .where(AppVersion.is_current.is_(True))
            .values(is_current=False)
        )

    version = AppVersion(
        version=data.version,
        version_code=data.versionCode,
        apk_url=apk_url,
        apk_filename=data.apkFilename,
        changelog=data.changelog,
        force_update=data.forceUpdate,
        min_supported_version_code=data.minSupportedVersionCode,
        is_current=data.isCurrent,
        published_at=datetime.now(timezone.utc),
    )
    db.add(version)
    await db.commit()
    await db.refresh(version)
    return _admin(version)


@router.patch(
    "/api/v1/admin/app-versions/{id}", summary="Отредактировать версию"
)
async def update_app_version(
    id: UUID,
    data: AppVersionUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _admin_user: Annotated[User, Depends(require_admin)],
):
    version = await db.get(AppVersion, id)
    if not version:
        raise HTTPException(status_code=404, detail="Версия не найдена.")

    if data.version is not None:
        version.version = data.version
    if data.changelog is not None:
        version.changelog = data.changelog
    if data.forceUpdate is not None:
        version.force_update = data.forceUpdate
    if data.minSupportedVersionCode is not None:
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
    if version.is_current:
        raise HTTPException(
            status_code=400, detail="Нельзя удалить текущую версию."
        )
    await db.delete(version)
    await db.commit()
    return {"status": "deleted"}
