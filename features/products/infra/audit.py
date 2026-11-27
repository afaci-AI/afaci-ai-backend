"""Адаптеры бизнес-аудита продуктов поверх журнала `core.audit`."""

from __future__ import annotations

from uuid import UUID

from core.audit.food_audit import (
    FOOD_ENTITY,
    log_food_event,
    snapshot_nutrient,
    snapshot_product,
)

from ..app.ports import Caller, NutrientRow, ProductRow


class FoodProductSnapshots:
    def of(self, row: ProductRow) -> dict:
        return snapshot_product(row)


class FoodNutrientSnapshots:
    def of(self, row: NutrientRow) -> dict:
        return snapshot_nutrient(row)


class FoodAuditLog:
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
