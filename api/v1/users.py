"""
Управление пользователями (доступно только администраторам).

  GET    /api/v1/users            — список (поиск/фильтр по роли)
  GET    /api/v1/users/{id}       — один пользователь
  POST   /api/v1/users            — создать
  PATCH  /api/v1/users/{id}       — редактировать (роль, статус, срок доступа)
  DELETE /api/v1/users/{id}           — деактивировать
  DELETE /api/v1/users/{id}/permanent — удалить безвозвратно вместе с сохранёнными рецептурами
"""

from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.audit.helpers import log_audit_change
from infrastructure.auth import hash_password, require_admin, user_public
from infrastructure.db.models import User
from infrastructure.db.session import get_db

router = APIRouter(prefix="/api/v1/users", tags=["Users"])

VALID_ROLES = {"admin", "editor", "viewer"}


class UserCreateRequest(BaseModel):
    email: str = Field(min_length=3)
    name: str = Field(min_length=1)
    password: str = Field(min_length=6)
    role: str = "viewer"
    access_expires_at: datetime | None = None
    must_change_password: bool = False


class UserUpdateRequest(BaseModel):
    name: str | None = None
    role: str | None = None
    is_active: bool | None = None
    access_expires_at: datetime | None = None
    access_expires_at_unlimited: bool | None = None  # True — сбросить срок в null


def _validate_role(role: str) -> None:
    if role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail=f"Недопустимая роль: {role}")


def _validate_expiry(expires_at: datetime | None) -> None:
    if expires_at is not None and expires_at <= datetime.now(timezone.utc):
        raise HTTPException(
            status_code=400, detail="Дата окончания доступа не может быть в прошлом."
        )


@router.get("", summary="Список пользователей")
async def list_users(
    db: Annotated[AsyncSession, Depends(get_db)],
    _admin: Annotated[User, Depends(require_admin)],
    search: str | None = None,
    role: str | None = None,
):
    query = select(User)
    if role:
        query = query.where(User.role == role)
    res = await db.execute(query.order_by(User.created_at.desc()))
    users = res.scalars().all()
    if search:
        s = search.lower()
        users = [u for u in users if s in u.email.lower() or s in u.name.lower()]
    return [user_public(u) for u in users]


@router.get("/{id}", summary="Пользователь по id")
async def get_user(
    id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _admin: Annotated[User, Depends(require_admin)],
):
    user = await db.get(User, id)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден.")
    return user_public(user)


@router.post("", status_code=201, summary="Создать пользователя")
async def create_user(
    data: UserCreateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    _admin: Annotated[User, Depends(require_admin)],
):
    _validate_role(data.role)
    _validate_expiry(data.access_expires_at)
    email = data.email.lower()
    exists = (
        await db.execute(select(User).where(User.email == email))
    ).scalar_one_or_none()
    if exists is not None:
        raise HTTPException(
            status_code=409, detail="Пользователь с таким email уже существует."
        )

    user = User(
        email=email,
        name=data.name.strip(),
        password_hash=hash_password(data.password),
        role=data.role,
        access_expires_at=data.access_expires_at,
        must_change_password=data.must_change_password,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user_public(user)


@router.patch("/{id}", summary="Редактировать пользователя")
async def update_user(
    id: UUID,
    data: UserUpdateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(require_admin)],
):
    user = await db.get(User, id)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден.")

    if data.role is not None:
        _validate_role(data.role)
        if user.id == admin.id and data.role != "admin":
            raise HTTPException(
                status_code=400,
                detail="Нельзя понизить роль собственной учётной записи.",
            )
        user.role = data.role

    if data.is_active is not None:
        if user.id == admin.id and not data.is_active:
            raise HTTPException(
                status_code=400,
                detail="Нельзя деактивировать собственную учётную запись.",
            )
        user.is_active = data.is_active

    if data.name is not None:
        user.name = data.name.strip()

    if data.access_expires_at_unlimited:
        user.access_expires_at = None
    elif data.access_expires_at is not None:
        _validate_expiry(data.access_expires_at)
        user.access_expires_at = data.access_expires_at

    await db.commit()
    await db.refresh(user)

    # --- Аудит мутации (ТЗ п.4): фиксируем кто и что изменил ---
    log_audit_change(
        action="update_user",
        target_type="User",
        target_id=str(id),
        changed_fields=data.model_dump(exclude_unset=True),
        actor=str(admin.id),
        extra={"target_email": user.email},
    )

    return user_public(user)


@router.delete("/{id}", summary="Деактивировать пользователя")
async def deactivate_user(
    id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(require_admin)],
):
    if id == admin.id:
        raise HTTPException(
            status_code=400, detail="Нельзя деактивировать собственную учётную запись."
        )
    user = await db.get(User, id)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден.")
    user.is_active = False
    await db.commit()
    return {"status": "deactivated"}


@router.delete(
    "/{id}/permanent", summary="Удалить пользователя безвозвратно вместе с рецептурами"
)
async def delete_user_permanently(
    id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(require_admin)],
):
    if id == admin.id:
        raise HTTPException(
            status_code=400, detail="Нельзя удалить собственную учётную запись."
        )
    user = await db.get(User, id)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден.")
    # cascade="all, delete-orphan" на User.groups/saved_recipes удаляет группы,
    # рецептуры и их ингредиенты (SavedRecipeItem каскадится от SavedRecipe).
    await db.delete(user)
    await db.commit()
    return {"status": "deleted"}
