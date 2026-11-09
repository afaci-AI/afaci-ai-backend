"""Сценарии продуктов и нутриентов с бизнес-аудитом изменений."""

from __future__ import annotations

from uuid import UUID

from core.errors import BadRequestError, NotFoundError, UnprocessableError
from features.catalog.domain.rules import (
    UnitRuleViolation,
    nutrient_unit_for,
)

from .ports import (
    AuditTrail,
    Caller,
    DuplicateError,
    NutrientRepository,
    ProductRepository,
    Row,
)

FOOD_CREATED = "FOOD_PRODUCT_CREATED"
FOOD_UPDATED = "FOOD_PRODUCT_UPDATED"
FOOD_DELETED = "FOOD_PRODUCT_DELETED"
FOOD_BULK_CREATED = "FOOD_PRODUCT_BULK_CREATED"


def _unit_for(name: Row, requested: UUID | None) -> UUID:
    try:
        return nutrient_unit_for(name.unit_id, requested)
    except UnitRuleViolation as exc:
        error = UnprocessableError if exc.code == "required" else BadRequestError
        raise error(exc.detail) from exc


def _bulk_changes(count: int, ids: list[str], **extra) -> dict:
    return {
        "old": None,
        "new": {
            "count": count,
            "target_ids": ids[:100],
            **extra,
            "truncated": len(ids) > 100,
        },
    }


class ProductService:
    def __init__(self, repo: ProductRepository, audit: AuditTrail) -> None:
        self._repo = repo
        self._audit = audit

    async def get(self, product_id: UUID) -> Row:
        item = await self._repo.get(product_id)
        if item is None:
            raise NotFoundError("Product not found")
        return item

    async def list(self) -> list[Row]:
        return await self._repo.list()

    async def count(self) -> int:
        return await self._repo.count()

    async def by_region(self, region_id: UUID) -> list[Row]:
        return await self._repo.by_region(region_id)

    async def by_category(self, category_id: UUID) -> list[Row]:
        return await self._repo.by_category(category_id)

    async def create(self, data: dict, caller: Caller) -> Row:
        try:
            item = await self._repo.add(data)
        except DuplicateError as exc:
            raise BadRequestError("Product already exists in this region") from exc
        self._audit.log(
            FOOD_CREATED,
            caller,
            item.id,
            {"old": None, "new": self._audit.snapshot_product(item)},
        )
        return item

    async def delete(self, product_id: UUID, caller: Caller) -> dict:
        item = await self.get(product_id)
        old_snapshot = self._audit.snapshot_product(item)
        await self._repo.delete(item)
        self._audit.log(
            FOOD_DELETED, caller, product_id, {"old": old_snapshot, "new": None}
        )
        return {"status": "deleted"}

    async def update(self, product_id: UUID, patch: dict, caller: Caller) -> Row:
        item = await self.get(product_id)
        old_snapshot = self._audit.snapshot_product(item)
        if not patch:
            return item
        try:
            await self._repo.update(item, patch)
        except DuplicateError as exc:
            raise BadRequestError("Product already exists in this region") from exc
        old_diff, new_diff = self._audit.diff(
            old_snapshot, self._audit.snapshot_product(item)
        )
        if old_diff:
            self._audit.log(
                FOOD_UPDATED, caller, product_id, {"old": old_diff, "new": new_diff}
            )
        return item

    async def bulk_create(self, items: list[dict], caller: Caller) -> dict:
        try:
            created = await self._repo.add_many(items)
        except DuplicateError as exc:
            raise BadRequestError(
                "Some products already exist or invalid data"
            ) from exc
        ids = [str(it.id) for it in created]
        # Одна запись на bulk — защита диска при сотнях позиций
        self._audit.log(
            FOOD_BULK_CREATED,
            caller,
            ids[0] if ids else "bulk",
            _bulk_changes(len(created), ids),
        )
        return {"inserted": len(created)}

    # ------------------------------------------------ автосоздание продуктов
    async def _auto_refs(self, data: dict) -> tuple[Row, Row, Row | None]:
        category = await self._repo.get_or_create_named(
            "category", data["category_name"]
        )
        region = await self._repo.get_or_create_named("region", data["region_name"])
        subcategory = None
        if data.get("subcategory_name"):
            subcategory = await self._repo.get_or_create_named(
                "subcategory", data["subcategory_name"]
            )
        return category, region, subcategory

    async def auto_create(self, data: dict, caller: Caller) -> Row:
        try:
            category, region, subcategory = await self._auto_refs(data)
            product = await self._repo.stage(
                {
                    "name": data["name"],
                    "category_id": category.id,
                    "region_id": region.id,
                    "subcategory_id": subcategory.id if subcategory else None,
                }
            )
            await self._repo.commit()
            await self._repo.refresh(product)
        except DuplicateError as exc:
            await self._repo.rollback()
            raise BadRequestError("Product already exists") from exc
        self._audit.log(
            FOOD_CREATED,
            caller,
            product.id,
            {"old": None, "new": self._audit.snapshot_product(product)},
        )
        return product

    async def auto_bulk(self, items: list[dict], caller: Caller) -> dict:
        created: list[Row] = []
        errors: list[str] = []
        for idx, data in enumerate(items):
            try:
                category, region, subcategory = await self._auto_refs(data)
                if await self._repo.find_in_region(data["name"], region.id):
                    errors.append(
                        f"Row {idx}: Product '{data['name']}' already exists in region"
                    )
                    continue
                created.append(
                    await self._repo.stage(
                        {
                            "name": data["name"],
                            "category_id": category.id,
                            "region_id": region.id,
                            "subcategory_id": subcategory.id if subcategory else None,
                        }
                    )
                )
            except Exception as e:  # noqa: BLE001
                errors.append(f"Row {idx}: {e!s}")

        try:
            await self._repo.commit()
        except DuplicateError:
            await self._repo.rollback()
            return {
                "warning": "Transaction rolled back due to conflict",
                "errors": errors,
            }

        if created:
            self._audit.log(
                FOOD_BULK_CREATED,
                caller,
                "bulk",
                _bulk_changes(len(created), [str(p.id) for p in created]),
            )
        return {"created": len(created), "errors": errors}


class NutrientService:
    def __init__(self, repo: NutrientRepository, audit: AuditTrail) -> None:
        self._repo = repo
        self._audit = audit

    async def get(self, nutrient_id: UUID) -> Row:
        item = await self._repo.get(nutrient_id)
        if item is None:
            raise NotFoundError("Nutrient not found")
        return item

    async def _name(self, name_id: UUID) -> Row:
        name = await self._repo.get_name(name_id)
        if name is None:
            raise NotFoundError("NutrientName not found")
        return name

    async def list(self) -> list[Row]:
        return await self._repo.list()

    async def by_product(self, product_id: UUID) -> list[Row]:
        return await self._repo.by_product(product_id)

    async def create(self, payload: dict, caller: Caller) -> Row:
        name = await self._repo.get_name(payload["nutrient_name_id"])
        if not name:
            raise NotFoundError("Nutrient name not found")
        payload["nutrient_type_id"] = name.nutrient_type_id
        payload["unit_id"] = _unit_for(name, payload.get("unit_id"))
        item = await self._repo.add(payload)
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
        await self._repo.delete(item)
        self._audit.log(
            FOOD_DELETED,
            caller,
            product_id,
            {"old": old_snapshot, "new": None, "nutrient_id": str(nutrient_id)},
        )
        return {"status": "deleted"}

    async def update(self, nutrient_id: UUID, patch: dict, caller: Caller) -> Row:
        item = await self.get(nutrient_id)
        old_snapshot = self._audit.snapshot_nutrient(item)
        if not patch:
            return item
        # Явный null вместо единицы означает «не менять».
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
        await self._repo.update(item, patch)
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

    async def bulk_create(self, payloads: list[dict], caller: Caller) -> dict:
        try:
            names = await self._repo.names_by_ids(
                {p["nutrient_name_id"] for p in payloads}
            )
            for p in payloads:
                name = names.get(p["nutrient_name_id"])
                if not name:
                    raise NotFoundError("Nutrient name not found")
                p["nutrient_type_id"] = name.nutrient_type_id
                p["unit_id"] = _unit_for(name, p.get("unit_id"))
            items = await self._repo.add_many(payloads)
        except DuplicateError as exc:
            raise BadRequestError("Duplicate nutrient entry detected") from exc
        nutrient_ids = [str(it.id) for it in items]
        product_ids = list({str(it.product_id) for it in items})
        self._audit.log(
            FOOD_BULK_CREATED,
            caller,
            product_ids[0] if product_ids else "bulk",
            _bulk_changes(len(items), nutrient_ids, product_ids=product_ids[:20]),
        )
        return {"inserted": len(items)}
