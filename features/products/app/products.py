"""Сценарии продуктов: чтение, создание, изменение, удаление, пачка."""

from __future__ import annotations

from uuid import UUID

from core.errors import BadRequestError, NotFoundError

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
    ProductRepository,
    ProductRow,
    UnitOfWork,
)
from .transaction import transaction

ALREADY_IN_REGION = "Product already exists in this region"


class ProductService:
    def __init__(
        self, repo: ProductRepository, uow: UnitOfWork, audit: AuditTrail
    ) -> None:
        self._repo = repo
        self._uow = uow
        self._audit = audit

    async def get(self, product_id: UUID) -> ProductRow:
        item = await self._repo.get(product_id)
        if item is None:
            raise NotFoundError("Product not found")
        return item

    async def list(self) -> list[ProductRow]:
        return await self._repo.list()

    async def count(self) -> int:
        return await self._repo.count()

    async def by_region(self, region_id: UUID) -> list[ProductRow]:
        return await self._repo.by_region(region_id)

    async def by_category(self, category_id: UUID) -> list[ProductRow]:
        return await self._repo.by_category(category_id)

    async def create(self, data: dict, caller: Caller) -> ProductRow:
        try:
            async with transaction(self._uow):
                item = await self._repo.add(data)
        except DuplicateError as exc:
            raise BadRequestError(ALREADY_IN_REGION) from exc
        await self._uow.refresh(item)
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
        async with transaction(self._uow):
            await self._repo.delete(item)
        self._audit.log(
            FOOD_DELETED, caller, product_id, {"old": old_snapshot, "new": None}
        )
        return {"status": "deleted"}

    async def update(self, product_id: UUID, patch: dict, caller: Caller) -> ProductRow:
        item = await self.get(product_id)
        old_snapshot = self._audit.snapshot_product(item)
        if not patch:
            return item
        try:
            async with transaction(self._uow):
                await self._repo.update(item, patch)
        except DuplicateError as exc:
            raise BadRequestError(ALREADY_IN_REGION) from exc
        await self._uow.refresh(item)
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
            async with transaction(self._uow):
                created = await self._repo.add_many(items)
        except DuplicateError as exc:
            raise BadRequestError(
                "Some products already exist or invalid data"
            ) from exc
        for row in created:
            await self._uow.refresh(row)
        ids = [str(it.id) for it in created]
        self._audit.log(
            FOOD_BULK_CREATED,
            caller,
            ids[0] if ids else "bulk",
            bulk_changes(len(created), ids),
        )
        return {"inserted": len(created)}
