"""Запись события изменения в журнал аудита.

Middleware НЕ логирует request.body — это делает явный вызов, чтобы избежать
утечки PII/паролей и проблем с чтением stream.

Пример (внутри сценария):
    log_audit_change(
        action="update_user",
        target_type="User",
        target_id=str(id),
        changed_fields=data.model_dump(exclude_unset=True),
        actor=str(admin.id),
    )
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from .logger import get_audit_logger
from .sanitize import sanitize, truncate


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
            "timestamp": datetime.now(UTC).isoformat(),
            "event": "audit.change",
            "action": action,
            "target_type": target_type,
            "target_id": str(target_id),
            "actor": str(actor) if actor is not None else "unknown",
        }
        if changed_fields is not None:
            payload["changed_fields"] = sanitize(changed_fields)
        if extra is not None:
            payload["extra"] = sanitize(extra)

        msg = truncate(json.dumps(payload, ensure_ascii=False, default=str))
        logger.log(level, msg)
    except Exception:  # noqa: BLE001,S110 — fail-safe: аудит не должен ронять запрос
        pass
