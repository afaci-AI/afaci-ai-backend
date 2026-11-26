"""Адаптер бизнес-аудита продуктов поверх журнала `core.audit`."""

from __future__ import annotations

from uuid import UUID

from core.audit.food_audit import (
    FOOD_ENTITY,
    compute_diff,
    log_food_event,
    snapshot_nutrient,
    snapshot_product,
)

from ..app.ports import Caller, NutrientRow, ProductRow


class FoodAuditTrail:
    def snapshot_product(self, row: ProductRow) -> dict:
        return snapshot_product(row)

    def snapshot_nutrient(self, row: NutrientRow) -> dict:
        return snapshot_nutrient(row)

    def diff(self, old: dict, new: dict) -> tuple[dict, dict]:
        return compute_diff(old, new)

    def log(
        self, event: str, caller: Caller, target_id: str | UUID, changes: dict
    ) -> None:
        log_food_event(
            event=event,
            user=caller.actor,
            target_entity=FOOD_ENTITY,
            target_id=target_id,
            changes=changes,
        )
