"""Автосоздание продуктов по именам справочников (одиночно и пачкой)."""

from __future__ import annotations

from typing import NamedTuple

from core.errors import BadRequestError
from core.transaction import transaction

from .audit_events import FOOD_BULK_CREATED, FOOD_CREATED, bulk_changes
from .ports import (
    AuditTrail,
    Caller,
    DuplicateError,
    ProductRepository,
    ProductRow,
    ReferenceNames,
    ReferenceRow,
    UnitOfWork,
)

BULK_CONFLICT = "Transaction rolled back due to conflict"


class AutoRefs(NamedTuple):
    """Справочники продукта, найденные или добавленные по имени."""

    category: ReferenceRow
    region: ReferenceRow
    subcategory: ReferenceRow | None


class ProductImportService:
    def __init__(
        self,
        repo: ProductRepository,
        names: ReferenceNames,
        uow: UnitOfWork,
        audit: AuditTrail,
    ) -> None:
        self._repo = repo
        self._names = names
        self._uow = uow
        self._audit = audit

    async def _refs(self, data: dict) -> AutoRefs:
        category = await self._names.category(data["category_name"])
        region = await self._names.region(data["region_name"])
        subcategory = None
        if data.get("subcategory_name"):
            subcategory = await self._names.subcategory(data["subcategory_name"])
        return AutoRefs(category, region, subcategory)

    async def _add(self, data: dict, refs: AutoRefs) -> ProductRow:
        return await self._repo.add(
            {
                "name": data["name"],
                "category_id": refs.category.id,
                "region_id": refs.region.id,
                "subcategory_id": refs.subcategory.id if refs.subcategory else None,
            }
        )

    async def auto_create(self, data: dict, caller: Caller) -> ProductRow:
        try:
            async with transaction(self._uow):
                product = await self._add(data, await self._refs(data))
        except DuplicateError as exc:
            raise BadRequestError("Product already exists") from exc
        await self._uow.refresh(product)
        self._audit.log(
            FOOD_CREATED,
            caller,
            product.id,
            {"old": None, "new": self._audit.snapshot_product(product)},
        )
        return product

    async def auto_bulk(self, items: list[dict], caller: Caller) -> dict:
        """Строки с уже существующим продуктом пропускаются с ошибкой в ответе.

        Конфликт уникальности откатывает всю пачку; прочие сбои тоже
        откатывают её и не подменяются текстом ошибки.
        """
        created: list[ProductRow] = []
        errors: list[str] = []
        try:
            async with transaction(self._uow):
                for idx, data in enumerate(items):
                    try:
                        refs = await self._refs(data)
                        if await self._repo.find_in_region(
                            data["name"], refs.region.id
                        ):
                            errors.append(
                                f"Row {idx}: Product '{data['name']}' "
                                "already exists in region"
                            )
                            continue
                        created.append(await self._add(data, refs))
                    except DuplicateError as exc:
                        errors.append(f"Row {idx}: {exc!s}")
                        raise
        except DuplicateError:
            return {"warning": BULK_CONFLICT, "errors": errors}

        if created:
            self._audit.log(
                FOOD_BULK_CREATED,
                caller,
                "bulk",
                bulk_changes(len(created), [str(p.id) for p in created]),
            )
        return {"created": len(created), "errors": errors}
