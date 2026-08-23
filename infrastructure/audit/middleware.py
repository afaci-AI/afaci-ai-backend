"""
Middleware аудита HTTP-слоя.

Перехватывает ВСЕ входящие запросы, собирает метрики и пишет JSON-лог.
Отказоустойчивость: любой сбой логгирования не влияет на ответ клиенту.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from infrastructure.audit.logger import get_audit_logger

# Эндпоинты-исключения — не засоряем логи служебным трафиком
EXCLUDE_PATHS: set[str] = {
    "/docs",
    "/redoc",
    "/openapi.json",
    "/healthcheck",
    "/health",
    "/favicon.ico",
}

# Префиксы для исключения вложенных путей (/docs/oauth2-redirect, /docs/*)
EXCLUDE_PREFIXES: tuple[str, ...] = (
    "/docs",
    "/redoc",
)


def _is_excluded(path: str) -> bool:
    if path in EXCLUDE_PATHS:
        return True
    for prefix in EXCLUDE_PREFIXES:
        if path == prefix or path.startswith(prefix + "/"):
            return True
    return False


def _extract_user(authorization: str | None) -> str:
    """Безопасное извлечение user из Authorization header.

    Returns:
        "Anonymous" — заголовка нет
        "InvalidToken" — заголовок есть но токен невалиден/не Bearer
        "user:<sub>" — валидный JWT
    """
    if not authorization:
        return "Anonymous"

    # Локальная реализация _extract_bearer чтобы не тянуть зависимость от БД
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return "InvalidToken"

    token = parts[1].strip()
    if not token:
        return "InvalidToken"

    # Используем decode_token из infrastructure.auth (только проверка подписи/срока)
    try:
        from infrastructure.auth import decode_token

        sub = decode_token(token)
        if sub is None:
            return "InvalidToken"
        return f"user:{sub}"
    except Exception:  # noqa: BLE001 — любой сбой декодирования -> InvalidToken, не ломаем запрос
        return "InvalidToken"


def _client_ip(request: Request) -> str:
    """Определяет IP клиента с учётом прокси (X-Forwarded-For)."""
    xff = request.headers.get("x-forwarded-for")
    if xff:
        # X-Forwarded-For: client, proxy1, proxy2
        first = xff.split(",")[0].strip()
        if first:
            return first
    x_real = request.headers.get("x-real-ip")
    if x_real:
        return x_real.strip()
    if request.client:
        return request.client.host
    return "unknown"


class AuditLogMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware для аудита всех HTTP-запросов.

    Собираемые метрики (ТЗ):
    - timestamp (ISO/UTC)
    - user ID / username
    - client IP
    - HTTP method
    - request path (с query string)
    - HTTP status code
    - duration_ms

    Использование:
        from infrastructure.audit.middleware import AuditLogMiddleware
        app.add_middleware(AuditLogMiddleware)
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # Исключаем служебные эндпоинты
        if _is_excluded(request.url.path):
            return await call_next(request)

        start = time.perf_counter()
        # Извлекаем пользователя ДО обработки запроса (не требует await)
        user = _extract_user(request.headers.get("authorization"))
        method = request.method
        # path + query для полноты аудита
        path = request.url.path
        if request.url.query:
            path = f"{path}?{request.url.query}"

        ip = _client_ip(request)

        status_code: int | None = None
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        except Exception:
            # Необработанное исключение — логируем как 500 и пробрасываем дальше
            # FastAPI всё равно вернёт 500, но нам важно зафиксировать
            status_code = 500
            raise
        finally:
            # Логирование в finally — гарантирует запись даже при exception
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            # Определяем статус если почему-то остался None
            if status_code is None:
                status_code = 500

            # Уровень по ТЗ
            if status_code < 400:
                level = logging.INFO
            elif status_code < 500:
                level = logging.WARNING
            else:
                level = logging.ERROR

            payload = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "user": user,
                "ip": ip,
                "method": method,
                "path": path,
                "status_code": status_code,
                "duration_ms": duration_ms,
            }

            # Отказоустойчивость: сбой логгера не ломает запрос
            try:
                logger = get_audit_logger()
                logger.log(level, json.dumps(payload, ensure_ascii=False))
            except Exception:  # noqa: BLE001,S110 — последний рубеж, игнор ошибки логгирования
                pass
