"""
Бизнес-аудит продуктов питания (Product / Nutrient).

Формат записи — JSON Lines через audit_logger (logs/audit.log + stdout):
{
  "timestamp": "2026-08-23T14:25:00.000000+00:00",
  "event": "FOOD_PRODUCT_UPDATED",
  "user": "user:uuid-or-id",
  "target_entity": "Product",
  "target_id": "product-uuid",
  "changes": {"old": {...}, "new": {...}}
}

События:
- FOOD_PRODUCT_CREATED — old=null, new=snapshot
- FOOD_PRODUCT_UPDATED — только изменившиеся поля (old!=new)
- FOOD_PRODUCT_DELETED — old=snapshot, new=null
- FOOD_PRODUCT_BULK_CREATED / BULK_UPDATED / BULK_DELETED — одна запись на bulk
  с count + target_ids (защита диска).

Scope: только Product/Nutrient, только мутации (GET игнорируется).
Отказоустойчивость: любой сбой логирования не ломает бизнес-транзакцию.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from infrastructure.audit.logger import get_audit_logger

# Ограничение для bulk — не пишем тысячи UUID в лог целиком
MAX_IDS_IN_LOG = 100
MAX_PAYLOAD_CHARS = 4000

FOOD_ENTITY = "Product"
NUTRIENT_ENTITY = "Product"  # Nutrient считается частью продукта (ТЗ п.2)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sanitize_value(value: Any) -> Any:
    if isinstance(value, UUID):
        return str(value)
    return value


def _truncate(payload_str: str) -> str:
    if len(payload_str) > MAX_PAYLOAD_CHARS:
        return payload_str[:MAX_PAYLOAD_CHARS] + "...(truncated)"
    return payload_str


def snapshot_product(product: Any) -> dict[str, Any]:
    """Снепшот Product для diff/old/new."""
    return {
        "name": _sanitize_value(getattr(product, "name", None)),
        "category_id": _sanitize_value(getattr(product, "category_id", None)),
        "subcategory_id": _sanitize_value(getattr(product, "subcategory_id", None)),
        "region_id": _sanitize_value(getattr(product, "region_id", None)),
    }


def snapshot_nutrient(nutrient: Any) -> dict[str, Any]:
    """Снепшот Nutrient — считается частью продукта."""
    return {
        "product_id": _sanitize_value(getattr(nutrient, "product_id", None)),
        "nutrient_name_id": _sanitize_value(
            getattr(nutrient, "nutrient_name_id", None)
        ),
        "nutrient_type_id": _sanitize_value(
            getattr(nutrient, "nutrient_type_id", None)
        ),
        "unit_id": _sanitize_value(getattr(nutrient, "unit_id", None)),
        "quantity": getattr(nutrient, "quantity", None),
        "error_rate": getattr(nutrient, "error_rate", None),
    }


def compute_diff(
    old: dict[str, Any], new: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Возвращает (old_diff, new_diff) — только поля где old != new."""
    old_diff: dict[str, Any] = {}
    new_diff: dict[str, Any] = {}
    keys = set(old.keys()) | set(new.keys())
    for key in keys:
        old_val = old.get(key)
        new_val = new.get(key)
        # Нормализуем UUID к str для сравнения
        if isinstance(old_val, UUID):
            old_val = str(old_val)
        if isinstance(new_val, UUID):
            new_val = str(new_val)
        if old_val != new_val:
            old_diff[key] = old_val
            new_diff[key] = new_val
    return old_diff, new_diff


def _resolve_user(current_user: Any | None, authorization: str | None) -> str:
    """Определяет user для лога: user:<id> / Anonymous / InvalidToken."""
    if current_user is not None:
        # User модель имеет id
        uid = getattr(current_user, "id", None)
        if uid is not None:
            return f"user:{uid}"
        return f"user:{current_user}"
    # Fallback без БД — как в middleware
    if not authorization:
        return "Anonymous"
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return "InvalidToken"
    token = parts[1].strip()
    if not token:
        return "InvalidToken"
    try:
        from infrastructure.auth import decode_token

        sub = decode_token(token)
        if sub is None:
            return "InvalidToken"
        return f"user:{sub}"
    except Exception:  # noqa: BLE001 — любой сбой -> InvalidToken
        return "InvalidToken"


def log_food_event(
    *,
    event: str,
    user: str,
    target_entity: str,
    target_id: str | UUID,
    changes: dict[str, Any],
) -> None:
    """Запись бизнес-аудита продукта. Fail-safe: никогда не бросает исключение."""
    try:
        logger = get_audit_logger()
        payload: dict[str, Any] = {
            "timestamp": _utc_now_iso(),
            "event": event,
            "user": user,
            "target_entity": target_entity,
            "target_id": str(target_id),
            "changes": changes,
        }
        msg = _truncate(json.dumps(payload, ensure_ascii=False, default=str))
        logger.log(logging.INFO, msg)
    except Exception:  # noqa: BLE001,S110 — аудит не должен ронять запрос
        pass


def resolve_food_user(current_user: Any | None, authorization: str | None) -> str:
    """Публичная обёртка для резолва user — используется в эндпоинтах."""
    return _resolve_user(current_user, authorization)
