"""SQL-реализации хранилищ продуктов и нутриентов на ORM-моделях."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from core.db import models

from ..app.ports import DuplicateError, Row

NAMED = {
    "category": models.Category,
    "region": models.Region,
    "subcategory": models.Subcategory,
}


class SqlProductRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get(self, product_id: UUID) -> Row | None:
        return await self._db.get(models.Product, product_id)

    async def list(self) -> list[Row]:
        res = await self._db.execute(select(models.Product))
        return list(res.scalars().all())

    async def count(self) -> int:
        total = await self._db.scalar(select(func.count()).select_from(models.Product))
        return total or 0

    async def by_region(self, region_id: UUID) -> list[Row]:
        res = await self._db.execute(
            select(models.Product).where(models.Product.region_id == region_id)
        )
        return list(res.scalars().all())

    async def by_category(self, category_id: UUID) -> list[Row]:
        res = await self._db.execute(
            select(models.Product).where(models.Product.category_id == category_id)
        )
        return list(res.scalars().all())

    async def add(self, data: dict) -> Row:
        try:
            item = models.Product(**data)
            self._db.add(item)
            await self._db.commit()
            await self._db.refresh(item)
            return item
        except IntegrityError as exc:
            await self._db.rollback()
            raise DuplicateError(str(exc)) from exc

    async def add_many(self, items: list[dict]) -> list[Row]:
        try:
            rows = [models.Product(**p) for p in items]
            self._db.add_all(rows)
            await self._db.commit()
            for row in rows:
                await self._db.refresh(row)
            return rows
        except IntegrityError as exc:
            await self._db.rollback()
            raise DuplicateError(str(exc)) from exc

    async def update(self, row: Row, patch: dict) -> Row:
        for field, value in patch.items():
            setattr(row, field, value)
        try:
            await self._db.commit()
            await self._db.refresh(row)
        except IntegrityError as exc:
            await self._db.rollback()
            raise DuplicateError(str(exc)) from exc
        return row

    async def delete(self, row: Row) -> None:
        await self._db.delete(row)
        await self._db.commit()

    # ------------------------------------------------ автосоздание продуктов
    async def get_or_create_named(self, kind: str, name: str) -> Row:
        model = NAMED[kind]
        res = await self._db.execute(select(model).where(model.name == name))
        item = res.scalar_one_or_none()
        if not item:
            item = model(name=name)
            self._db.add(item)
            await self._flush()
        return item

    async def find_in_region(self, name: str, region_id: UUID) -> Row | None:
        res = await self._db.execute(
            select(models.Product).where(
                models.Product.name == name,
                models.Product.region_id == region_id,
            )
        )
        return res.scalar_one_or_none()

    async def stage(self, data: dict) -> Row:
        product = models.Product(**data)
        self._db.add(product)
        await self._flush()
        return product

    async def _flush(self) -> None:
        try:
            await self._db.flush()
        except IntegrityError as exc:
            raise DuplicateError(str(exc)) from exc

    async def commit(self) -> None:
        try:
            await self._db.commit()
        except IntegrityError as exc:
            raise DuplicateError(str(exc)) from exc

    async def rollback(self) -> None:
        await self._db.rollback()

    async def refresh(self, row: Row) -> None:
        await self._db.refresh(row)


class SqlNutrientRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get(self, nutrient_id: UUID) -> Row | None:
        return await self._db.get(models.Nutrient, nutrient_id)

    async def list(self) -> list[Row]:
        res = await self._db.execute(select(models.Nutrient))
        return list(res.scalars().all())

    async def by_product(self, product_id: UUID) -> list[Row]:
        res = await self._db.execute(
            select(models.Nutrient).where(models.Nutrient.product_id == product_id)
        )
        return list(res.scalars().all())

    async def get_name(self, name_id: UUID) -> Row | None:
        return await self._db.get(models.NutrientName, name_id)

    async def names_by_ids(self, ids: set[UUID]) -> dict[UUID, Row]:
        names = await self._db.scalars(
            select(models.NutrientName).where(models.NutrientName.id.in_(ids))
        )
        return {n.id: n for n in names}

    async def add(self, data: dict) -> Row:
        item = models.Nutrient(**data)
        self._db.add(item)
        await self._db.commit()
        await self._db.refresh(item)
        return item

    async def add_many(self, items: list[dict]) -> list[Row]:
        try:
            rows = [models.Nutrient(**n) for n in items]
            self._db.add_all(rows)
            await self._db.commit()
            for row in rows:
                await self._db.refresh(row)
            return rows
        except IntegrityError as exc:
            await self._db.rollback()
            raise DuplicateError(str(exc)) from exc

    async def update(self, row: Row, patch: dict) -> Row:
        for field, value in patch.items():
            setattr(row, field, value)
        await self._db.commit()
        await self._db.refresh(row)
        return row

    async def delete(self, row: Row) -> None:
        await self._db.delete(row)
        await self._db.commit()
