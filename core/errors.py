"""Общие прикладные ошибки: use-case'ы бросают их, HTTP-код назначает слой api.

`register_error_handlers` превращает ошибку в ответ `{"detail": ...}` с кодом
ошибки — тот же формат, что у `HTTPException`.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    status_code = 500

    def __init__(self, detail: Any = None) -> None:
        self.detail = detail
        super().__init__(str(detail))


class BadRequestError(AppError):
    status_code = 400


class UnauthorizedError(AppError):
    status_code = 401


class ForbiddenError(AppError):
    status_code = 403


class NotFoundError(AppError):
    status_code = 404


class ConflictError(AppError):
    status_code = 409


class UnprocessableError(AppError):
    status_code = 422


async def _handle_app_error(_request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _handle_app_error)
