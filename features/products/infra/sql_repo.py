"""SQL-реализации хранилищ продуктов и нутриентов на ORM-моделях.

Хранилища только отправляют изменения в сессию (`flush`); фиксирует и
откатывает транзакцию `SqlUnitOfWork` по решению сценария.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from core.db import models

from ..app.ports import (
    DuplicateError,
    NutrientNameRow,
    NutrientRow,
    ProductRow,
    ReferenceRow,
)


async def _flush(db: AsyncSession) -> None:
    try:
        await db.flush()
    except IntegrityError as exc:
        raise DuplicateError(str(exc)) from exc


class SqlProductRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get(self, product_id: UUID) -> ProductRow | None:
        return await self._db.get(models.Product, product_id)

    async def list(self) -> list[ProductRow]:
        res = await self._db.execute(select(models.Product))
        return list(res.scalars().all())

    async def count(self) -> int:
        total = await self._db.scalar(select(func.count()).select_from(models.Product))
        return total or 0

    async def by_region(self, region_id: UUID) -> list[ProductRow]:
        res = await self._db.execute(
            select(models.Product).where(models.Product.region_id == region_id)
        )
        return list(res.scalars().all())

    async def by_category(self, category_id: UUID) -> list[ProductRow]:
        res = await self._db.execute(
            select(models.Product).where(models.Product.category_id == category_id)
        )
        return list(res.scalars().all())

    async def add(self, data: dict) -> ProductRow:
        item = models.Product(**data)
        self._db.add(item)
        await _flush(self._db)
        return item

    async def add_many(self, items: list[dict]) -> list[ProductRow]:
        rows = [models.Product(**p) for p in items]
        self._db.add_all(rows)
        await _flush(self._db)
        return rows

    async def update(self, row: ProductRow, patch: dict) -> ProductRow:
        for field, value in patch.items():
            setattr(row, field, value)
        await _flush(self._db)
        return row

    async def delete(self, row: ProductRow) -> None:
        await self._db.delete(row)
        await _flush(self._db)

    async def find_in_region(self, name: str, region_id: UUID) -> ProductRow | None:
        res = await self._db.execute(
            select(models.Product).where(
                models.Product.name == name,
                models.Product.region_id == region_id,
            )
        )
        return res.scalar_one_or_none()


class SqlReferenceNames:
    """Категории, регионы и подкатегории по имени; новые — без фиксации."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def _named(self, model, name: str) -> ReferenceRow:
        res = await self._db.execute(select(model).where(model.name == name))
        item = res.scalar_one_or_none()
        if not item:
            item = model(name=name)
            self._db.add(item)
            await _flush(self._db)
        return item

    async def category(self, name: str) -> ReferenceRow:
        return await self._named(models.Category, name)

    async def region(self, name: str) -> ReferenceRow:
        return await self._named(models.Region, name)

    async def subcategory(self, name: str) -> ReferenceRow:
        return await self._named(models.Subcategory, name)


class SqlUnitOfWork:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def commit(self) -> None:
        try:
            await self._db.commit()
        except IntegrityError as exc:
            raise DuplicateError(str(exc)) from exc

    async def rollback(self) -> None:
        await self._db.rollback()

    async def refresh(self, row: object) -> None:
        await self._db.refresh(row)


class SqlNutrientRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get(self, nutrient_id: UUID) -> NutrientRow | None:
        return await self._db.get(models.Nutrient, nutrient_id)

    async def list(self) -> list[NutrientRow]:
        res = await self._db.execute(select(models.Nutrient))
        return list(res.scalars().all())

    async def by_product(self, product_id: UUID) -> list[NutrientRow]:
        res = await self._db.execute(
            select(models.Nutrient).where(models.Nutrient.product_id == product_id)
        )
        return list(res.scalars().all())

    async def get_name(self, name_id: UUID) -> NutrientNameRow | None:
        return await self._db.get(models.NutrientName, name_id)

    async def names_by_ids(self, ids: set[UUID]) -> dict[UUID, NutrientNameRow]:
        names = await self._db.scalars(
            select(models.NutrientName).where(models.NutrientName.id.in_(ids))
        )
        return {n.id: n for n in names}

    async def add(self, data: dict) -> NutrientRow:
        item = models.Nutrient(**data)
        self._db.add(item)
        await _flush(self._db)
        return item

    async def add_many(self, items: list[dict]) -> list[NutrientRow]:
        rows = [models.Nutrient(**n) for n in items]
        self._db.add_all(rows)
        await _flush(self._db)
        return rows

    async def update(self, row: NutrientRow, patch: dict) -> NutrientRow:
        for field, value in patch.items():
            setattr(row, field, value)
        await _flush(self._db)
        return row

    async def delete(self, row: NutrientRow) -> None:
        await self._db.delete(row)
        await _flush(self._db)
