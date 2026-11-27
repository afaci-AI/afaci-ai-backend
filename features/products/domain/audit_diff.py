"""Что изменилось между двумя снимками записи."""

from __future__ import annotations

from typing import Any
from uuid import UUID


def _comparable(value: Any) -> Any:
    return str(value) if isinstance(value, UUID) else value


def changed_fields(
    old: dict[str, Any], new: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    """(old_diff, new_diff) — только поля, где значения различаются."""
    old_diff: dict[str, Any] = {}
    new_diff: dict[str, Any] = {}
    for key in old.keys() | new.keys():
        old_value, new_value = _comparable(old.get(key)), _comparable(new.get(key))
        if old_value != new_value:
            old_diff[key] = old_value
            new_diff[key] = new_value
    return old_diff, new_diff
