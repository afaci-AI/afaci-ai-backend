"""
Хелперы для логирования деталей изменений (Payload / Diff).

Используются внутри мутирующих эндпоинтов POST/PUT/PATCH/DELETE.
Middleware НЕ логирует request.body — это делает явный вызов helper-а,
чтобы избежать утечки PII/паролей и проблем с чтением stream.

Пример (внутри роутера):
    from infrastructure.audit.helpers import log_audit_change

    @router.patch("/users/{id}")
    async def update_user(...):
        changed = data.model_dump(exclude_unset=True)
        # ... применяем изменения ...
        log_audit_change(
            action="update_user",
            target_type="User",
            target_id=str(id),
            changed_fields=changed,
            actor=str(admin.id),  # или admin.email
            extra={"role_old": old_role}
        )
"""

from __future__ import annotations

import functools
import json
import logging
from datetime import datetime, timezone
from typing import Any, Callable
from uuid import UUID

from infrastructure.audit.logger import get_audit_logger

# Поля которые никогда не логируем (PII/секреты)
SENSITIVE_FIELDS: set[str] = {
    "password",
    "password_hash",
    "current_password",
    "new_password",
    "secret",
    "token",
    "access_token",
    "refresh_token",
}

MAX_PAYLOAD_CHARS = 4000  # защита от гигантских diff


def _sanitize(data: dict[str, Any] | None) -> dict[str, Any] | None:
    if not data:
        return data
    sanitized = {}
    for k, v in data.items():
        if k.lower() in SENSITIVE_FIELDS:
            sanitized[k] = "***"
        else:
            # UUID -> str для JSON
            if isinstance(v, UUID):
                v = str(v)
            sanitized[k] = v
    return sanitized


def _truncate(payload_str: str) -> str:
    if len(payload_str) > MAX_PAYLOAD_CHARS:
        return payload_str[:MAX_PAYLOAD_CHARS] + "...(truncated)"
    return payload_str


def log_audit_change(
    *,
    action: str,
    target_type: str,
    target_id: str | UUID | int,
    changed_fields: dict[str, Any] | None = None,
    actor: str | UUID | None = None,
    extra: dict[str, Any] | None = None,
    level: int = logging.INFO,
) -> None:
    """Логирует детальное изменение.

    Args:
        action: действие, напр. "update_user", "delete_product"
        target_type: тип сущности, напр. "User", "Product"
        target_id: идентификатор цели
        changed_fields: словарь изменённых полей {"role": "admin"}
        actor: кто совершил действие (user id/email). Если None — "unknown"
        extra: доп. контекст (старые значения, request_id и т.п.)
        level: уровень логирования (по умолчанию INFO)
    """
    try:
        logger = get_audit_logger()
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": "audit.change",
            "action": action,
            "target_type": target_type,
            "target_id": str(target_id),
            "actor": str(actor) if actor is not None else "unknown",
        }
        if changed_fields is not None:
            payload["changed_fields"] = _sanitize(changed_fields)
        if extra is not None:
            payload["extra"] = _sanitize(extra)

        msg = _truncate(json.dumps(payload, ensure_ascii=False, default=str))
        logger.log(level, msg)
    except Exception:
        # Отказоустойчивость: сбой аудита изменений не ломает бизнес-логику
        pass


def audit_log(
    action: str,
    target_type: str,
    *,
    target_id_arg: str = "id",
    changed_fields_arg: str | None = None,
    actor_arg: str | None = None,
) -> Callable:
    """Декоратор для автоматического логирования изменений.

    Интроспектирует аргументы функции и логирует их.

    Пример:
        @router.patch("/users/{id}")
        @audit_log("update_user", "User", target_id_arg="id", changed_fields_arg="data", actor_arg="admin")
        async def update_user(id: UUID, data: UserUpdateRequest, admin: User = Depends(require_admin)):
            ...

    Args:
        action: имя действия
        target_type: тип сущности
        target_id_arg: имя аргумента с ID цели
        changed_fields_arg: имя аргумента с Pydantic моделью / dict изменений (будет вызван model_dump если есть)
        actor_arg: имя аргумента с актором (User или str). Если None — пытается найти admin/current/current_user.
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):  # type: ignore[no-untyped-def]
            # Извлекаем значения из kwargs (FastAPI передаёт через kwargs)
            bound = _bind_args(func, args, kwargs)

            target_id = bound.get(target_id_arg, "unknown")

            # Извлечение changed_fields
            changed = None
            if changed_fields_arg and changed_fields_arg in bound:
                raw = bound[changed_fields_arg]
                if raw is not None:
                    if hasattr(raw, "model_dump"):
                        try:
                            changed = raw.model_dump(exclude_unset=True)  # Pydantic v2
                        except TypeError:
                            changed = raw.model_dump()
                    elif hasattr(raw, "dict"):
                        try:
                            changed = raw.dict(exclude_unset=True)  # Pydantic v1
                        except TypeError:
                            changed = raw.dict()
                    elif isinstance(raw, dict):
                        changed = raw
                    else:
                        changed = {"value": str(raw)}

            # Извлечение actor
            actor = None
            if actor_arg and actor_arg in bound:
                actor = bound[actor_arg]
            else:
                # Эвристика: ищем admin/current/current_user
                for key in ("admin", "current", "current_user", "_admin", "user"):
                    if key in bound:
                        actor = bound[key]
                        break

            # Нормализация actor к строке
            actor_str: str | None = None
            if actor is not None:
                if hasattr(actor, "id"):
                    actor_str = str(actor.id)
                elif hasattr(actor, "email"):
                    actor_str = str(actor.email)
                else:
                    actor_str = str(actor)

            result = await func(*args, **kwargs)

            # Логируем ПОСЛЕ успешного выполнения (если endpoint бросил HTTPException — не логируем)
            try:
                log_audit_change(
                    action=action,
                    target_type=target_type,
                    target_id=target_id,
                    changed_fields=changed,
                    actor=actor_str,
                )
            except Exception:
                pass

            return result

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):  # type: ignore[no-untyped-def]
            # Поддержка синхронных функций (если вдруг)
            bound = _bind_args(func, args, kwargs)
            target_id = bound.get(target_id_arg, "unknown")
            changed = None
            if changed_fields_arg and changed_fields_arg in bound:
                raw = bound[changed_fields_arg]
                if isinstance(raw, dict):
                    changed = raw
                elif hasattr(raw, "model_dump"):
                    changed = raw.model_dump(exclude_unset=True)
                elif hasattr(raw, "dict"):
                    changed = raw.dict(exclude_unset=True)
            actor = None
            if actor_arg and actor_arg in bound:
                actor = bound[actor_arg]
            else:
                for key in ("admin", "current", "current_user", "_admin", "user"):
                    if key in bound:
                        actor = bound[key]
                        break
            actor_str = None
            if actor is not None:
                actor_str = str(getattr(actor, "id", actor))
            result = func(*args, **kwargs)
            try:
                log_audit_change(
                    action=action,
                    target_type=target_type,
                    target_id=target_id,
                    changed_fields=changed,
                    actor=actor_str,
                )
            except Exception:
                pass
            return result

        # Выбираем обёртку по типу функции
        import inspect

        if inspect.iscoroutinefunction(func):
            return async_wrapper  # type: ignore[return-value]
        return sync_wrapper  # type: ignore[return-value]

    return decorator


def _bind_args(func: Callable, args: tuple, kwargs: dict) -> dict[str, Any]:
    """Связывает args/kwargs с именами параметров функции."""
    import inspect

    try:
        sig = inspect.signature(func)
        bound = sig.bind_partial(*args, **kwargs)
        bound.apply_defaults()
        return dict(bound.arguments)
    except Exception:
        # Fallback: только kwargs
        return dict(kwargs)
