"""Схемы запросов справочников."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from ..app import (
    NewNutrientName,
    NewSubcategory,
    NutrientNameChanges,
    SubcategoryChanges,
)

NutrientClass = Literal["macro", "micro", "amino", "other"]


class SimpleCreate(BaseModel):
    name: str


class SimpleUpdate(BaseModel):
    name: str | None = None


class SubcategoryCreate(SimpleCreate):
    category_id: UUID

    def command(self) -> NewSubcategory:
        return NewSubcategory(name=self.name, category_id=self.category_id)


class SubcategoryUpdate(SimpleUpdate):
    category_id: UUID | None = None

    def changes(self) -> SubcategoryChanges:
        return SubcategoryChanges(
            name=self.name,
            category_id=self.category_id,
            provided=frozenset(self.model_fields_set),
        )


class NutrientNameCreate(SimpleCreate):
    nutrient_type_id: UUID
    # Не указана — единица берётся по правилу типа состава.
    unit_id: UUID | None = None
    # Не указан — класс берётся по типу состава.
    nutrient_class: NutrientClass | None = None

    def command(self) -> NewNutrientName:
        return NewNutrientName(
            name=self.name,
            nutrient_type_id=self.nutrient_type_id,
            unit_id=self.unit_id,
            nutrient_class=self.nutrient_class,
        )


class NutrientNameUpdate(SimpleUpdate):
    nutrient_type_id: UUID | None = None
    unit_id: UUID | None = None
    nutrient_class: NutrientClass | None = None

    def changes(self) -> NutrientNameChanges:
        return NutrientNameChanges(
            name=self.name,
            nutrient_type_id=self.nutrient_type_id,
            unit_id=self.unit_id,
            nutrient_class=self.nutrient_class,
            provided=frozenset(self.model_fields_set),
        )


class SimpleBulkCreate(BaseModel):
    names: list[str]
