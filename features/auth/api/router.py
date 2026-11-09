"""
Эндпоинты аутентификации.

  POST /api/v1/auth/login            — вход, возвращает JWT
  GET  /api/v1/auth/me               — текущий пользователь
  POST /api/v1/auth/change-password  — смена пароля
"""

from typing import Annotated

from fastapi import APIRouter, Depends

from core.db.models import User
from core.security import get_current_user, user_public

from ..app import AuthService
from .deps import get_auth_service
from .schemas import ChangePasswordRequest, LoginRequest

router = APIRouter(prefix="/api/v1/auth", tags=["Auth"])

Service = Annotated[AuthService, Depends(get_auth_service)]


@router.post("/login", summary="Вход")
async def login(req: LoginRequest, service: Service):
    token, user = await service.login(req.email, req.password)
    return {"access_token": token, "user": user_public(user)}


@router.get("/me", summary="Текущий пользователь")
async def me(current: Annotated[User, Depends(get_current_user)]):
    return user_public(current)


@router.post("/change-password", summary="Смена пароля")
async def change_password(
    req: ChangePasswordRequest,
    current: Annotated[User, Depends(get_current_user)],
    service: Service,
):
    return await service.change_password(
        current, req.current_password, req.new_password
    )
