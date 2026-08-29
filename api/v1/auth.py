"""
Эндпоинты аутентификации.

  POST /api/v1/auth/register  — регистрация (email, name, password)
  POST /api/v1/auth/login     — вход, возвращает JWT
  GET  /api/v1/auth/me        — текущий пользователь
"""

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.auth import (
    create_access_token,
    get_current_user,
    hash_password,
    is_expired,
    user_public,
    verify_password,
)
from infrastructure.db.models import User
from infrastructure.db.session import get_db

router = APIRouter(prefix="/api/v1/auth", tags=["Auth"])


class RegisterRequest(BaseModel):
    email: str = Field(min_length=3)
    name: str = Field(min_length=1)
    password: str = Field(min_length=6)


class LoginRequest(BaseModel):
    email: str
    password: str


@router.post("/register", summary="Регистрация пользователя")
async def register(req: RegisterRequest, db: Annotated[AsyncSession, Depends(get_db)]):
    email = req.email.lower()
    exists = (
        await db.execute(select(User).where(User.email == email))
    ).scalar_one_or_none()
    if exists is not None:
        raise HTTPException(
            status_code=409, detail="Пользователь с таким email уже существует."
        )

    user = User(
        email=email,
        name=req.name.strip(),
        password_hash=hash_password(req.password),
        role="viewer",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return {"access_token": create_access_token(user.id), "user": user_public(user)}


@router.post("/login", summary="Вход")
async def login(req: LoginRequest, db: Annotated[AsyncSession, Depends(get_db)]):
    email = req.email.lower()
    user = (
        await db.execute(select(User).where(User.email == email))
    ).scalar_one_or_none()
    if user is None or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Неверный email или пароль.")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Учётная запись отключена.")
    if is_expired(user):
        raise HTTPException(
            status_code=403,
            detail="Срок действия учётной записи истёк. Обратитесь в техническую поддержку.",
        )

    user.last_login_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(user)
    return {"access_token": create_access_token(user.id), "user": user_public(user)}


@router.get("/me", summary="Текущий пользователь")
async def me(current: Annotated[User, Depends(get_current_user)]):
    return user_public(current)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=6)


@router.post("/change-password", summary="Смена пароля")
async def change_password(
    req: ChangePasswordRequest,
    current: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    if not verify_password(req.current_password, current.password_hash):
        raise HTTPException(status_code=401, detail="Неверный текущий пароль.")
    current.password_hash = hash_password(req.new_password)
    current.must_change_password = False
    await db.commit()
    return {"status": "ok"}
