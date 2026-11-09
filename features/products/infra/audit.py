"""Адаптер бизнес-аудита продуктов поверх журнала `infrastructure.audit`."""

from __future__ import annotations

from uuid import UUID

from infrastructure.audit.food_audit import (
    FOOD_ENTITY,
    compute_diff,
    log_food_event,
    resolve_food_user,
    snapshot_nutrient,
    snapshot_product,
)

from ..app.ports import Caller, Row


class FoodAuditTrail:
    def snapshot_product(self, row: Row) -> dict:
        return snapshot_product(row)

    def snapshot_nutrient(self, row: Row) -> dict:
        return snapshot_nutrient(row)

    def diff(self, old: dict, new: dict) -> tuple[dict, dict]:
        return compute_diff(old, new)

    def log(
        self, event: str, caller: Caller, target_id: str | UUID, changes: dict
    ) -> None:
        log_food_event(
            event=event,
            user=resolve_food_user(caller.user, caller.authorization),
            target_entity=FOOD_ENTITY,
            target_id=target_id,
            changes=changes,
        )
