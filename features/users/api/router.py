"""
Управление пользователями (доступно только администраторам).

  GET    /api/v1/users            — список (поиск/фильтр по роли)
  GET    /api/v1/users/{id}       — один пользователь
  POST   /api/v1/users            — создать
  PATCH  /api/v1/users/{id}       — редактировать (роль, статус, срок доступа)
  DELETE /api/v1/users/{id}           — деактивировать
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from core.db.models import User
from core.security import require_admin, user_public

from ..app import UserService
from .deps import get_user_service
from .schemas import UserCreateRequest, UserUpdateRequest

router = APIRouter(prefix="/api/v1/users", tags=["Users"])

Service = Annotated[UserService, Depends(get_user_service)]
Admin = Annotated[User, Depends(require_admin)]


@router.get("", summary="Список пользователей")
async def list_users(
    service: Service,
    _admin: Admin,
    search: str | None = None,
    role: str | None = None,
):
    return [user_public(u) for u in await service.list(role, search)]


@router.get("/{id}", summary="Пользователь по id")
async def get_user(id: UUID, service: Service, _admin: Admin):
    return user_public(await service.get(id))


@router.post("", status_code=201, summary="Создать пользователя")
async def create_user(data: UserCreateRequest, service: Service, _admin: Admin):
    return user_public(await service.create(data.model_dump()))


@router.patch("/{id}", summary="Редактировать пользователя")
async def update_user(
    id: UUID, data: UserUpdateRequest, service: Service, admin: Admin
):
    user = await service.update(id, data.model_dump(exclude_unset=True), admin.id)
    return user_public(user)


@router.delete("/{id}", summary="Деактивировать пользователя")
async def deactivate_user(id: UUID, service: Service, admin: Admin):
    return await service.deactivate(id, admin.id)
