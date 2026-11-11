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

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile

from core.db.models import User
from core.rate_limit import limiter
from core.security import require_admin

from ..app import AppVersionService
from .deps import get_app_version_service
from .presenters import admin, public
from .schemas import AppVersionAdmin, AppVersionCreate, AppVersionUpdate

router = APIRouter(tags=["App Version"])

Service = Annotated[AppVersionService, Depends(get_app_version_service)]
Admin = Annotated[User, Depends(require_admin)]


# ----------------------- публичный эндпоинт -----------------------
@router.get("/api/v1/app/version", summary="Текущая версия приложения")
@limiter.limit("30/minute")
async def get_app_version(request: Request, service: Service):
    return public(await service.current())


# ------------------------- загрузка APK ---------------------------
@router.post(
    "/api/v1/admin/app-versions/upload-apk",
    status_code=201,
    summary="Загрузить APK и опубликовать версию",
    response_model=AppVersionAdmin,
)
async def upload_apk(
    _admin_user: Admin,
    file: Annotated[UploadFile, File()],
    service: Service,
    forceUpdate: Annotated[bool, Form()] = False,
    changelog: Annotated[str | None, Form()] = None,
    minSupportedVersionCode: Annotated[int | None, Form(ge=0)] = None,
):
    version = await service.upload(
        original_name=file.filename,
        read_chunk=file.read,
        force_update=forceUpdate,
        changelog=changelog,
        min_supported_version_code=minSupportedVersionCode,
    )
    return admin(version)


# ------------------------- управление -----------------------------
@router.get("/api/v1/admin/app-versions", summary="Список всех версий")
async def list_app_versions(service: Service, _admin_user: Admin):
    return [admin(v) for v in await service.list()]


@router.post("/api/v1/admin/app-versions", status_code=201, summary="Создать версию")
async def create_app_version(
    data: AppVersionCreate, service: Service, _admin_user: Admin
):
    return admin(await service.create(data.model_dump()))


@router.patch("/api/v1/admin/app-versions/{id}", summary="Отредактировать версию")
async def update_app_version(
    id: UUID, data: AppVersionUpdate, service: Service, _admin_user: Admin
):
    return admin(await service.update(id, data.model_dump(exclude_unset=True)))


@router.patch(
    "/api/v1/admin/app-versions/{id}/current",
    summary="Назначить версию текущей",
)
async def set_current_app_version(id: UUID, service: Service, _admin_user: Admin):
    return admin(await service.set_current(id))


@router.delete("/api/v1/admin/app-versions/{id}", summary="Удалить версию")
async def delete_app_version(id: UUID, service: Service, _admin_user: Admin):
    return await service.delete(id)
