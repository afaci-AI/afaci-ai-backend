"""
Аутентификация: хеширование паролей (bcrypt), JWT-токены (PyJWT)
и FastAPI-зависимости для получения текущего пользователя.
"""

import os
from datetime import datetime, timedelta, timezone
from typing import Annotated
from uuid import UUID

import bcrypt
import jwt
from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.db.models import User
from infrastructure.db.session import get_db

JWT_SECRET = os.getenv("JWT_SECRET", "change-me-in-production")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(
    os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "10080")
)  # 7 дней


# ----------------------------- пароли -----------------------------
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


# ----------------------------- токены -----------------------------
def create_access_token(user_id: UUID) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": str(user_id), "exp": expire}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> str | None:
    """Вернуть user_id (str) из валидного токена либо None."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload.get("sub")
    except jwt.PyJWTError:
        return None


def _extract_bearer(authorization: str | None) -> str | None:
    if not authorization:
        return None
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return parts[1].strip()


# ----------------------- срок действия доступа ----------------------
def is_expired(user: User) -> bool:
    """access_expires_at = null значит безлимитный доступ."""
    return (
        user.access_expires_at is not None
        and user.access_expires_at <= datetime.now(timezone.utc)
    )


def user_status(user: User) -> str:
    if not user.is_active:
        return "blocked"
    if is_expired(user):
        return "expired"
    if user.access_expires_at is None:
        return "unlimited"
    return "active"


# -------------------------- зависимости ---------------------------
async def get_current_user(
    db: Annotated[AsyncSession, Depends(get_db)],
    authorization: str | None = Header(default=None),
) -> User:
    token = _extract_bearer(authorization)
    if not token:
        raise HTTPException(status_code=401, detail="Требуется авторизация.")
    user_id = decode_token(token)
    if not user_id:
        raise HTTPException(
            status_code=401, detail="Недействительный или истёкший токен."
        )
    user = (
        await db.execute(select(User).where(User.id == UUID(user_id)))
    ).scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=401, detail="Пользователь не найден или отключён."
        )
    if is_expired(user):
        # Проверка на каждом запросе: истёкший срок доступа = принудительный логаут.
        raise HTTPException(
            status_code=401,
            detail="Срок действия учётной записи истёк. Обратитесь в техническую поддержку.",
        )
    return user


async def require_admin(current: Annotated[User, Depends(get_current_user)]) -> User:
    if current.role != "admin":
        raise HTTPException(status_code=403, detail="Требуются права администратора.")
    return current


async def get_current_user_optional(
    db: Annotated[AsyncSession, Depends(get_db)],
    authorization: str | None = Header(default=None),
) -> User | None:
    token = _extract_bearer(authorization)
    if not token:
        return None
    user_id = decode_token(token)
    if not user_id:
        return None
    return (
        await db.execute(select(User).where(User.id == UUID(user_id)))
    ).scalar_one_or_none()


def user_public(user: User) -> dict:
    """Сериализация пользователя для фронтенда (без пароля)."""
    return {
        "id": str(user.id),
        "email": user.email,
        "name": user.name,
        "role": user.role,
        "isActive": user.is_active,
        "accessExpiresAt": user.access_expires_at.isoformat()
        if user.access_expires_at
        else None,
        "mustChangePassword": user.must_change_password,
        "status": user_status(user),
        "createdAt": user.created_at.isoformat() if user.created_at else None,
        "lastLoginAt": user.last_login_at.isoformat() if user.last_login_at else None,
    }
