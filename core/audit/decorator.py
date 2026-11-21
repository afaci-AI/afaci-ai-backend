"""Декоратор `audit_log`: автоматическая запись изменения после успешного вызова.

Пример:
    @router.patch("/users/{id}")
    @audit_log("update_user", "User", target_id_arg="id", changed_fields_arg="data", actor_arg="admin")
    async def update_user(id: UUID, data: UserUpdateRequest, admin: User = Depends(require_admin)):
        ...
"""

from __future__ import annotations

import functools
import inspect
from collections.abc import Callable
from typing import Any

from .events import log_audit_change

ACTOR_ARGUMENT_NAMES = ("admin", "current", "current_user", "_admin", "user")


def _bind_args(func: Callable, args: tuple, kwargs: dict) -> dict[str, Any]:
    """Связывает args/kwargs с именами параметров функции."""
    try:
        sig = inspect.signature(func)
        bound = sig.bind_partial(*args, **kwargs)
        bound.apply_defaults()
        return dict(bound.arguments)
    except Exception:  # noqa: BLE001 — fallback на kwargs при ошибке inspect
        return dict(kwargs)


def _dump(raw: Any, method: str) -> dict:
    try:
        return getattr(raw, method)(exclude_unset=True)
    except TypeError:
        return getattr(raw, method)()


def _changed_fields(raw: Any) -> dict | None:
    """Изменения из Pydantic-модели (v2 или v1), словаря или иного значения."""
    if raw is None:
        return None
    if hasattr(raw, "model_dump"):
        return _dump(raw, "model_dump")
    if hasattr(raw, "dict"):
        return _dump(raw, "dict")
    if isinstance(raw, dict):
        return raw
    return {"value": str(raw)}


def _actor(bound: dict[str, Any], actor_arg: str | None) -> str | None:
    """Актор: заданный аргумент либо первый из admin/current/current_user/..."""
    actor = None
    if actor_arg and actor_arg in bound:
        actor = bound[actor_arg]
    else:
        for key in ACTOR_ARGUMENT_NAMES:
            if key in bound:
                actor = bound[key]
                break
    if actor is None:
        return None
    if hasattr(actor, "id"):
        return str(actor.id)
    if hasattr(actor, "email"):
        return str(actor.email)
    return str(actor)


def audit_log(
    action: str,
    target_type: str,
    *,
    target_id_arg: str = "id",
    changed_fields_arg: str | None = None,
    actor_arg: str | None = None,
) -> Callable:
    """Декоратор для автоматического логирования изменений.

    Args:
        action: имя действия
        target_type: тип сущности
        target_id_arg: имя аргумента с ID цели
        changed_fields_arg: имя аргумента с Pydantic моделью / dict изменений
        actor_arg: имя аргумента с актором (User или str). Если None — ищется
            admin/current/current_user.
    """

    def decorator(func: Callable) -> Callable:
        def describe(args: tuple, kwargs: dict) -> dict:
            bound = _bind_args(func, args, kwargs)
            raw = bound.get(changed_fields_arg) if changed_fields_arg else None
            return {
                "action": action,
                "target_type": target_type,
                "target_id": bound.get(target_id_arg, "unknown"),
                "changed_fields": _changed_fields(raw),
                "actor": _actor(bound, actor_arg),
            }

        def record(event: dict) -> None:
            # Логируем ПОСЛЕ успешного выполнения (если endpoint бросил исключение — нет)
            try:
                log_audit_change(**event)
            except Exception:  # noqa: BLE001,S110 — fail-safe: аудит не должен ронять запрос
                pass

        if inspect.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                event = describe(args, kwargs)
                result = await func(*args, **kwargs)
                record(event)
                return result

            return async_wrapper

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            event = describe(args, kwargs)
            result = func(*args, **kwargs)
            record(event)
            return result

        return sync_wrapper

    return decorator
