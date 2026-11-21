"""
Аутентификация: хеширование паролей (bcrypt), JWT-токены (PyJWT)
и FastAPI-зависимости для получения текущего пользователя.
"""

import hashlib
import hmac
import os
from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

import bcrypt
import jwt
from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.models import User
from core.db.session import get_db

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


def hash_reset_code(user_id: UUID, code: str) -> str:
    """HMAC кода восстановления: 6 цифр нельзя перебрать по утёкшей БД без секрета."""
    message = f"{user_id}:{code}".encode()
    return hmac.new(JWT_SECRET.encode(), message, hashlib.sha256).hexdigest()


# ----------------------------- токены -----------------------------
def create_access_token(user_id: UUID, version: int = 0) -> str:
    """`ver` — версия токенов пользователя; при её росте токен отклоняется."""
    expire = datetime.now(UTC) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": str(user_id), "ver": version, "exp": expire}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def _decode(token: str) -> tuple[UUID, int] | None:
    """(user_id, версия токена) из валидного токена либо None."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return UUID(payload["sub"]), int(payload.get("ver", 0))
    except (jwt.PyJWTError, KeyError, TypeError, ValueError):
        return None


def decode_token(token: str) -> str | None:
    """Вернуть user_id (str) из валидного токена либо None."""
    claims = _decode(token)
    return str(claims[0]) if claims else None


def token_is_current(user: User, version: int) -> bool:
    """Токены, выпущенные до восстановления пароля, больше не принимаются."""
    return version == (user.token_version or 0)


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
        and user.access_expires_at <= datetime.now(UTC)
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
    claims = _decode(token)
    if not claims:
        raise HTTPException(
            status_code=401, detail="Недействительный или истёкший токен."
        )
    user_id, version = claims
    user = (
        await db.execute(select(User).where(User.id == user_id))
    ).scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=401, detail="Пользователь не найден или отключён."
        )
    if not token_is_current(user, version):
        raise HTTPException(
            status_code=401,
            detail="Сессия завершена после смены пароля. Войдите снова.",
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


async def require_editor(current: Annotated[User, Depends(get_current_user)]) -> User:
    if current.role not in {"admin", "editor"}:
        raise HTTPException(status_code=403, detail="Требуются права редактора.")
    return current


async def get_current_user_optional(
    db: Annotated[AsyncSession, Depends(get_db)],
    authorization: str | None = Header(default=None),
) -> User | None:
    token = _extract_bearer(authorization)
    if not token:
        return None
    claims = _decode(token)
    if not claims:
        return None
    user = (
        await db.execute(select(User).where(User.id == claims[0]))
    ).scalar_one_or_none()
    if user is None or not token_is_current(user, claims[1]):
        return None
    return user


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
