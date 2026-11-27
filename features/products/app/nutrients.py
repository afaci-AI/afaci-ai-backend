"""Сценарии нутриентов продукта: единица по названию нутриента и бизнес-аудит."""

from __future__ import annotations

from uuid import UUID

from core.errors import BadRequestError, NotFoundError, UnprocessableError
from core.transaction import transaction
from features.catalog.domain.rules import UnitRuleViolation, nutrient_unit_for

from .audit_events import (
    FOOD_BULK_CREATED,
    FOOD_CREATED,
    FOOD_DELETED,
    FOOD_UPDATED,
    bulk_changes,
)
from .ports import (
    AuditTrail,
    Caller,
    DuplicateError,
    NutrientNameRow,
    NutrientRepository,
    NutrientRow,
    UnitOfWork,
)

DUPLICATE_NUTRIENT = "Duplicate nutrient entry detected"


def _unit_for(name: NutrientNameRow, requested: UUID | None) -> UUID:
    try:
        return nutrient_unit_for(name.unit_id, requested)
    except UnitRuleViolation as exc:
        error = UnprocessableError if exc.code == "required" else BadRequestError
        raise error(exc.detail) from exc


class NutrientService:
    def __init__(
        self, repo: NutrientRepository, uow: UnitOfWork, audit: AuditTrail
    ) -> None:
        self._repo = repo
        self._uow = uow
        self._audit = audit

    async def get(self, nutrient_id: UUID) -> NutrientRow:
        item = await self._repo.get(nutrient_id)
        if item is None:
            raise NotFoundError("Nutrient not found")
        return item

    async def _name(self, name_id: UUID) -> NutrientNameRow:
        name = await self._repo.get_name(name_id)
        if name is None:
            raise NotFoundError("NutrientName not found")
        return name

    async def list(self) -> list[NutrientRow]:
        return await self._repo.list()

    async def by_product(self, product_id: UUID) -> list[NutrientRow]:
        return await self._repo.by_product(product_id)

    async def create(self, payload: dict, caller: Caller) -> NutrientRow:
        name = await self._repo.get_name(payload["nutrient_name_id"])
        if not name:
            raise NotFoundError("Nutrient name not found")
        payload["nutrient_type_id"] = name.nutrient_type_id
        payload["unit_id"] = _unit_for(name, payload.get("unit_id"))
        try:
            async with transaction(self._uow):
                item = await self._repo.add(payload)
        except DuplicateError as exc:
            raise BadRequestError(DUPLICATE_NUTRIENT) from exc
        await self._uow.refresh(item)
        self._audit.log(
            FOOD_CREATED,
            caller,
            item.product_id,
            {
                "old": None,
                "new": self._audit.snapshot_nutrient(item),
                "nutrient_id": str(item.id),
            },
        )
        return item

    async def delete(self, nutrient_id: UUID, caller: Caller) -> dict:
        item = await self.get(nutrient_id)
        old_snapshot = self._audit.snapshot_nutrient(item)
        product_id = item.product_id
        async with transaction(self._uow):
            await self._repo.delete(item)
        self._audit.log(
            FOOD_DELETED,
            caller,
            product_id,
            {"old": old_snapshot, "new": None, "nutrient_id": str(nutrient_id)},
        )
        return {"status": "deleted"}

    async def _apply_name_and_unit(self, item: NutrientRow, patch: dict) -> None:
        """Тип и единица следуют за названием; явный null единицы — «не менять»."""
        requested_unit = patch.pop("unit_id", None)
        name = None
        if "nutrient_name_id" in patch:
            if patch["nutrient_name_id"] is None:
                raise UnprocessableError("Nutrient name is required")
            name = await self._name(patch["nutrient_name_id"])
            patch["nutrient_type_id"] = name.nutrient_type_id
        elif requested_unit is not None:
            name = await self._name(item.nutrient_name_id)
        if name is not None:
            patch["unit_id"] = _unit_for(name, requested_unit)

    async def update(
        self, nutrient_id: UUID, patch: dict, caller: Caller
    ) -> NutrientRow:
        item = await self.get(nutrient_id)
        old_snapshot = self._audit.snapshot_nutrient(item)
        if not patch:
            return item
        await self._apply_name_and_unit(item, patch)
        try:
            async with transaction(self._uow):
                await self._repo.update(item, patch)
        except DuplicateError as exc:
            raise BadRequestError(DUPLICATE_NUTRIENT) from exc
        await self._uow.refresh(item)
        old_diff, new_diff = self._audit.diff(
            old_snapshot, self._audit.snapshot_nutrient(item)
        )
        if old_diff:
            self._audit.log(
                FOOD_UPDATED,
                caller,
                item.product_id,
                {"old": old_diff, "new": new_diff, "nutrient_id": str(nutrient_id)},
            )
        return item

    async def _resolve_names(self, payloads: list[dict]) -> None:
        names = await self._repo.names_by_ids({p["nutrient_name_id"] for p in payloads})
        for p in payloads:
            name = names.get(p["nutrient_name_id"])
            if not name:
                raise NotFoundError("Nutrient name not found")
            p["nutrient_type_id"] = name.nutrient_type_id
            p["unit_id"] = _unit_for(name, p.get("unit_id"))

    async def bulk_create(self, payloads: list[dict], caller: Caller) -> dict:
        await self._resolve_names(payloads)
        try:
            async with transaction(self._uow):
                items = await self._repo.add_many(payloads)
        except DuplicateError as exc:
            raise BadRequestError(DUPLICATE_NUTRIENT) from exc
        for row in items:
            await self._uow.refresh(row)
        nutrient_ids = [str(it.id) for it in items]
        product_ids = list({str(it.product_id) for it in items})
        self._audit.log(
            FOOD_BULK_CREATED,
            caller,
            product_ids[0] if product_ids else "bulk",
            bulk_changes(len(items), nutrient_ids, product_ids=product_ids[:20]),
        )
        return {"inserted": len(items)}
