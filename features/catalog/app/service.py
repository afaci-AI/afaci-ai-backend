"""Сценарии справочников: простые (имя) и специальные (подкатегории, названия нутриентов)."""

from __future__ import annotations

from uuid import UUID

from core.errors import BadRequestError, NotFoundError, UnprocessableError

from ..domain.dictionaries import (
    NUTRIENT_NAME_KIND,
    SUBCATEGORY_KIND,
    DictionarySpec,
)
from ..domain.rules import UNIT_CHANGE_FORBIDDEN, UNIT_REQUIRED, UNIT_REQUIRED_FOR_TYPE
from .ports import CatalogRepository, DuplicateError, InUseError, Row

CATEGORY_KIND = "category"
NUTRIENT_TYPE_KIND = "nutrient_type"
UNIT_KIND = "unit"

_MODEL_NAMES = {
    CATEGORY_KIND: "Category",
    NUTRIENT_TYPE_KIND: "NutrientType",
    UNIT_KIND: "Unit",
    SUBCATEGORY_KIND: "Subcategory",
    NUTRIENT_NAME_KIND: "NutrientName",
}


class CatalogService:
    def __init__(self, repo: CatalogRepository) -> None:
        self._repo = repo

    # ------------------------------------------------------------ общее
    async def get(self, kind: str, item_id: UUID, model_name: str | None = None) -> Row:
        item = await self._repo.get(kind, item_id)
        if item is None:
            raise NotFoundError(f"{model_name or _MODEL_NAMES[kind]} not found")
        return item

    async def _create(self, kind: str, data: dict, model_name: str):
        try:
            return await self._repo.add(kind, data)
        except DuplicateError as exc:
            raise BadRequestError(f"{model_name} already exists") from exc

    # --------------------------------------------------- простые справочники
    async def create(self, spec: DictionarySpec, data: dict) -> Row:
        return await self._create(spec.kind, data, spec.model_name)

    async def list(self, spec: DictionarySpec, name: str | None = None) -> list[Row]:
        return await self._repo.list(spec.kind, name if spec.searchable else None)

    async def get_one(self, spec: DictionarySpec, item_id: UUID) -> Row:
        return await self.get(spec.kind, item_id, spec.model_name)

    async def delete(self, spec: DictionarySpec, item_id: UUID) -> dict:
        item = await self.get_one(spec, item_id)
        try:
            await self._repo.delete(item)
        except InUseError as exc:
            raise BadRequestError(spec.in_use_message) from exc
        return {"status": "deleted"}

    async def rename(self, spec: DictionarySpec, item_id: UUID, name: str | None):
        item = await self.get_one(spec, item_id)
        if name is not None and name != item.name:
            if await self._repo.find_by_name(spec.kind, name):
                raise BadRequestError(spec.same_name_message)
            item.name = name
        return await self._repo.save(item)

    async def bulk(self, spec: DictionarySpec | str, names: list[str]) -> dict:
        kind = spec if isinstance(spec, str) else spec.kind
        inserted = 0
        skipped = 0
        for name in names:
            if await self._repo.find_by_name(kind, name) is None:
                self._repo.stage(kind, {"name": name})
                inserted += 1
            else:
                skipped += 1
        if inserted > 0:
            await self._repo.commit()
        return {"inserted": inserted, "skipped_duplicates": skipped}

    # ----------------------------------------------------------- подкатегории
    async def create_subcategory(self, data: dict) -> Row:
        await self.get(CATEGORY_KIND, data["category_id"])
        return await self._create(SUBCATEGORY_KIND, data, "Subcategory")

    async def update_subcategory(
        self, item_id: UUID, *, name: str | None, category_id, provided: set[str]
    ) -> Row:
        item = await self.get(SUBCATEGORY_KIND, item_id)
        if "category_id" in provided and category_id is None:
            raise UnprocessableError("Category is required")
        category_id = category_id or item.category_id
        await self.get(CATEGORY_KIND, category_id)
        name = name if name is not None else item.name
        if await self._repo.duplicate_subcategory(category_id, name, item_id):
            raise BadRequestError("Subcategory already exists in this category")
        item.name = name
        item.category_id = category_id
        try:
            return await self._repo.save(item)
        except DuplicateError as exc:
            raise BadRequestError(
                "Subcategory already exists in this category"
            ) from exc

    # ------------------------------------------------- названия нутриентов
    async def create_nutrient_name(self, data: dict) -> Row:
        nutrient_type = await self.get(NUTRIENT_TYPE_KIND, data["nutrient_type_id"])
        if data.get("unit_id") is not None:
            await self.get(UNIT_KIND, data["unit_id"])
        else:
            data["unit_id"] = await self._repo.default_unit_id(nutrient_type.name)
            if data["unit_id"] is None:
                raise UnprocessableError(UNIT_REQUIRED_FOR_TYPE)
        return await self._create(NUTRIENT_NAME_KIND, data, "NutrientName")

    async def update_nutrient_name(
        self,
        item_id: UUID,
        *,
        name: str | None,
        nutrient_type_id,
        unit_id,
        provided: set[str],
    ) -> Row:
        item = await self.get(NUTRIENT_NAME_KIND, item_id)
        if "nutrient_type_id" in provided and nutrient_type_id is None:
            raise UnprocessableError("Nutrient type is required")
        type_id = nutrient_type_id or item.nutrient_type_id
        await self.get(NUTRIENT_TYPE_KIND, type_id)
        name = name if name is not None else item.name
        if await self._repo.duplicate_nutrient_name(type_id, name, item_id):
            raise BadRequestError("Nutrient name already exists in this type")
        new_unit_id = item.unit_id
        if "unit_id" in provided:
            if unit_id is None:
                raise UnprocessableError(UNIT_REQUIRED)
            if unit_id != item.unit_id:
                await self.get(UNIT_KIND, unit_id)
                # Значения не пересчитываются: единицу можно менять, только если
                # ни одно сохранённое значение не записано в другой единице.
                if await self._repo.has_values_in_other_unit(item_id, unit_id):
                    raise BadRequestError(UNIT_CHANGE_FORBIDDEN)
            new_unit_id = unit_id
        item.name = name
        item.nutrient_type_id = type_id
        item.unit_id = new_unit_id
        try:
            return await self._repo.save(item)
        except DuplicateError as exc:
            raise BadRequestError("Nutrient name already exists in this type") from exc
