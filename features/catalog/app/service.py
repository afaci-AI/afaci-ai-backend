"""Сценарии справочников: простые (имя) и специальные (подкатегории, названия нутриентов).

Вид справочника — всегда его описание `DictionarySpec`: оно несёт ключ
хранилища и тексты ошибок, поэтому новый справочник не требует правок здесь.
Транзакцию фиксирует только единица работы (`transaction`).
"""

from __future__ import annotations

from typing import cast
from uuid import UUID

from core.errors import BadRequestError, NotFoundError, UnprocessableError

from ..domain.dictionaries import (
    CATEGORIES,
    NUTRIENT_NAMES,
    NUTRIENT_TYPES,
    SUBCATEGORIES,
    UNITS,
    DictionarySpec,
)
from ..domain.nutrient_classes import default_nutrient_class
from ..domain.rules import UNIT_CHANGE_FORBIDDEN, UNIT_REQUIRED, UNIT_REQUIRED_FOR_TYPE
from .ports import (
    CatalogRules,
    DictionaryRepository,
    DictionaryRow,
    DuplicateError,
    InUseError,
    NutrientNameRow,
    SubcategoryRow,
    UnitOfWork,
)
from .transaction import transaction

SUBCATEGORY_EXISTS = "Subcategory already exists in this category"
NUTRIENT_NAME_EXISTS = "Nutrient name already exists in this type"


class CatalogService:
    def __init__(
        self, repo: DictionaryRepository, rules: CatalogRules, uow: UnitOfWork
    ) -> None:
        self._repo = repo
        self._rules = rules
        self._uow = uow

    # ------------------------------------------------------------ общее
    async def get(self, spec: DictionarySpec, item_id: UUID) -> DictionaryRow:
        item = await self._repo.get(spec.kind, item_id)
        if item is None:
            raise NotFoundError(spec.not_found_message)
        return item

    async def list(
        self, spec: DictionarySpec, name: str | None = None
    ) -> list[DictionaryRow]:
        return await self._repo.list(spec.kind, name if spec.searchable else None)

    async def create(self, spec: DictionarySpec, data: dict) -> DictionaryRow:
        try:
            async with transaction(self._uow):
                item = await self._repo.add(spec.kind, data)
        except DuplicateError as exc:
            raise BadRequestError(spec.duplicate_message) from exc
        await self._uow.refresh(item)
        return item

    async def delete(self, spec: DictionarySpec, item_id: UUID) -> dict:
        item = await self.get(spec, item_id)
        try:
            async with transaction(self._uow):
                await self._repo.delete(item)
        except InUseError as exc:
            raise BadRequestError(spec.in_use_message) from exc
        return {"status": "deleted"}

    async def rename(
        self, spec: DictionarySpec, item_id: UUID, name: str | None
    ) -> DictionaryRow:
        item = await self.get(spec, item_id)
        if name is not None and name != item.name:
            if await self._repo.find_by_name(spec.kind, name):
                raise BadRequestError(spec.same_name_message)
            item.name = name
        return await self._save(item, spec.duplicate_message)

    async def bulk(self, spec: DictionarySpec, names: list[str]) -> dict:
        inserted = 0
        try:
            async with transaction(self._uow):
                for name in names:
                    if await self._repo.find_by_name(spec.kind, name) is None:
                        await self._repo.add(spec.kind, {"name": name})
                        inserted += 1
        except DuplicateError as exc:
            raise BadRequestError(spec.duplicate_message) from exc
        return {"inserted": inserted, "skipped_duplicates": len(names) - inserted}

    async def _save(self, item: DictionaryRow, duplicate_message: str) -> DictionaryRow:
        try:
            async with transaction(self._uow):
                await self._repo.save(item)
        except DuplicateError as exc:
            raise BadRequestError(duplicate_message) from exc
        await self._uow.refresh(item)
        return item

    # ----------------------------------------------------------- подкатегории
    async def create_subcategory(self, data: dict) -> DictionaryRow:
        await self.get(CATEGORIES, data["category_id"])
        return await self.create(SUBCATEGORIES, data)

    async def update_subcategory(
        self, item_id: UUID, *, name: str | None, category_id, provided: set[str]
    ) -> DictionaryRow:
        item = cast(SubcategoryRow, await self.get(SUBCATEGORIES, item_id))
        if "category_id" in provided and category_id is None:
            raise UnprocessableError("Category is required")
        category_id = category_id or item.category_id
        await self.get(CATEGORIES, category_id)
        name = name if name is not None else item.name
        if await self._rules.duplicate_subcategory(category_id, name, item_id):
            raise BadRequestError(SUBCATEGORY_EXISTS)
        item.name = name
        item.category_id = category_id
        return await self._save(item, SUBCATEGORY_EXISTS)

    # ------------------------------------------------- названия нутриентов
    async def create_nutrient_name(self, data: dict) -> DictionaryRow:
        nutrient_type = await self.get(NUTRIENT_TYPES, data["nutrient_type_id"])
        if data.get("unit_id") is not None:
            await self.get(UNITS, data["unit_id"])
        else:
            data["unit_id"] = await self._rules.default_unit_id(nutrient_type.name)
            if data["unit_id"] is None:
                raise UnprocessableError(UNIT_REQUIRED_FOR_TYPE)
        if data.get("nutrient_class") is None:
            data["nutrient_class"] = default_nutrient_class(nutrient_type.name)
        return await self.create(NUTRIENT_NAMES, data)

    async def update_nutrient_name(
        self,
        item_id: UUID,
        *,
        name: str | None,
        nutrient_type_id,
        unit_id,
        nutrient_class: str | None = None,
        provided: set[str],
    ) -> DictionaryRow:
        item = cast(NutrientNameRow, await self.get(NUTRIENT_NAMES, item_id))
        if "nutrient_type_id" in provided and nutrient_type_id is None:
            raise UnprocessableError("Nutrient type is required")
        type_id = nutrient_type_id or item.nutrient_type_id
        await self.get(NUTRIENT_TYPES, type_id)
        name = name if name is not None else item.name
        if await self._rules.duplicate_nutrient_name(type_id, name, item_id):
            raise BadRequestError(NUTRIENT_NAME_EXISTS)
        new_unit_id = (
            await self._checked_unit(item, unit_id)
            if "unit_id" in provided
            else item.unit_id
        )
        item.name = name
        item.nutrient_type_id = type_id
        item.unit_id = new_unit_id
        if nutrient_class is not None:
            item.nutrient_class = nutrient_class
        return await self._save(item, NUTRIENT_NAME_EXISTS)

    async def _checked_unit(self, item: NutrientNameRow, unit_id: UUID | None) -> UUID:
        """Новая единица названия, если её можно поставить."""
        if unit_id is None:
            raise UnprocessableError(UNIT_REQUIRED)
        if unit_id != item.unit_id:
            await self.get(UNITS, unit_id)
            # Значения не пересчитываются: единицу можно менять, только если
            # ни одно сохранённое значение не записано в другой единице.
            if await self._rules.has_values_in_other_unit(item.id, unit_id):
                raise BadRequestError(UNIT_CHANGE_FORBIDDEN)
        return unit_id
