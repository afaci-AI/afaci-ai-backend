"""Очистка данных перед записью в журнал аудита: секреты скрываются, UUID → строка."""

from __future__ import annotations

from typing import Any
from uuid import UUID

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


def sanitize(data: dict[str, Any] | None) -> dict[str, Any] | None:
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


def truncate(payload_str: str) -> str:
    if len(payload_str) > MAX_PAYLOAD_CHARS:
        return payload_str[:MAX_PAYLOAD_CHARS] + "...(truncated)"
    return payload_str
