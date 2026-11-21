"""
Эндпоинты аутентификации.

  POST /api/v1/auth/login            — вход, возвращает JWT
  GET  /api/v1/auth/me               — текущий пользователь
  POST /api/v1/auth/change-password  — смена пароля
  POST /api/v1/auth/password-reset/request  — код восстановления на почту
  POST /api/v1/auth/password-reset/verify   — проверка кода (не расходует его)
  POST /api/v1/auth/password-reset/confirm  — новый пароль по коду
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from core.db.models import User
from core.rate_limit import limiter
from core.security import get_current_user_pending_password, user_public

from ..app import AuthService, PasswordResetService
from .deps import get_auth_service, get_password_reset_service
from .schemas import (
    ChangePasswordRequest,
    LoginRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    PasswordResetVerify,
)

router = APIRouter(prefix="/api/v1/auth", tags=["Auth"])

Service = Annotated[AuthService, Depends(get_auth_service)]
ResetService = Annotated[PasswordResetService, Depends(get_password_reset_service)]


@router.post("/login", summary="Вход")
async def login(req: LoginRequest, service: Service):
    token, user = await service.login(req.email, req.password)
    return {"access_token": token, "user": user_public(user)}


@router.get("/me", summary="Текущий пользователь")
async def me(current: Annotated[User, Depends(get_current_user_pending_password)]):
    return user_public(current)


@router.post("/change-password", summary="Смена пароля")
async def change_password(
    req: ChangePasswordRequest,
    current: Annotated[User, Depends(get_current_user_pending_password)],
    service: Service,
):
    return await service.change_password(
        current, req.current_password, req.new_password
    )


@router.post("/password-reset/request", summary="Запросить код восстановления")
@limiter.limit("5/minute;20/hour")
async def request_password_reset(
    request: Request, req: PasswordResetRequest, service: ResetService
):
    return await service.request(req.email)


@router.post("/password-reset/verify", summary="Проверить код восстановления")
@limiter.limit("10/minute")
async def verify_password_reset(
    request: Request, req: PasswordResetVerify, service: ResetService
):
    return await service.verify(req.email, req.code)


@router.post("/password-reset/confirm", summary="Новый пароль по коду")
@limiter.limit("10/minute")
async def confirm_password_reset(
    request: Request, req: PasswordResetConfirm, service: ResetService
):
    return await service.confirm(req.email, req.code, req.new_password)
