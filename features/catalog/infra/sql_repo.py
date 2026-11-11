"""SQL-реализация хранилища справочников на ORM-моделях."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from core.db import models

from ..app.ports import DuplicateError, InUseError, Row
from ..domain.nutrient_units import default_unit_name

MODELS = {
    "category": models.Category,
    "subcategory": models.Subcategory,
    "region": models.Region,
    "unit": models.Unit,
    "nutrient_type": models.NutrientType,
    "nutrient_name": models.NutrientName,
}


class SqlCatalogRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get(self, kind: str, item_id: UUID) -> Row | None:
        return await self._db.get(MODELS[kind], item_id)

    async def list(self, kind: str, name: str | None = None) -> list[Row]:
        model = MODELS[kind]
        query = select(model)
        if name:
            query = query.where(model.name.ilike(f"%{name}%"))
        return list((await self._db.execute(query)).scalars().all())

    async def find_by_name(self, kind: str, name: str) -> Row | None:
        model = MODELS[kind]
        res = await self._db.execute(select(model).where(model.name == name))
        return res.scalar_one_or_none()

    async def add(self, kind: str, data: dict) -> Row:
        try:
            item = MODELS[kind](**data)
            self._db.add(item)
            await self._db.commit()
            await self._db.refresh(item)
            return item
        except IntegrityError as exc:
            await self._db.rollback()
            raise DuplicateError from exc

    def stage(self, kind: str, data: dict) -> Row:
        item = MODELS[kind](**data)
        self._db.add(item)
        return item

    async def save(self, row: Row) -> Row:
        try:
            await self._db.commit()
        except IntegrityError as exc:
            await self._db.rollback()
            raise DuplicateError from exc
        await self._db.refresh(row)
        return row

    async def commit(self) -> None:
        await self._db.commit()

    async def delete(self, row: Row) -> None:
        try:
            await self._db.delete(row)
            await self._db.commit()
        except IntegrityError as exc:
            await self._db.rollback()
            raise InUseError from exc

    async def default_unit_id(self, type_name: str) -> UUID | None:
        unit_name = default_unit_name(type_name)
        if unit_name is None:
            return None
        return await self._db.scalar(
            select(models.Unit.id).where(models.Unit.name == unit_name)
        )

    async def duplicate_subcategory(
        self, category_id: UUID, name: str, exclude_id: UUID
    ) -> bool:
        found = await self._db.scalar(
            select(models.Subcategory).where(
                models.Subcategory.category_id == category_id,
                models.Subcategory.name == name,
                models.Subcategory.id != exclude_id,
            )
        )
        return found is not None

    async def duplicate_nutrient_name(
        self, type_id: UUID, name: str, exclude_id: UUID
    ) -> bool:
        found = await self._db.scalar(
            select(models.NutrientName).where(
                models.NutrientName.nutrient_type_id == type_id,
                models.NutrientName.name == name,
                models.NutrientName.id != exclude_id,
            )
        )
        return found is not None

    async def has_values_in_other_unit(self, name_id: UUID, unit_id: UUID) -> bool:
        conflicting = await self._db.scalar(
            select(models.Nutrient.id)
            .where(
                models.Nutrient.nutrient_name_id == name_id,
                models.Nutrient.unit_id != unit_id,
            )
            .limit(1)
        )
        return conflicting is not None
