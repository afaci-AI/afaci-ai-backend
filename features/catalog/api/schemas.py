"""Схемы запросов справочников."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel

NutrientClass = Literal["macro", "micro", "amino", "other"]


class SimpleCreate(BaseModel):
    name: str


class SimpleUpdate(BaseModel):
    name: str | None = None


class SubcategoryCreate(SimpleCreate):
    category_id: UUID


class SubcategoryUpdate(SimpleUpdate):
    category_id: UUID | None = None


class NutrientNameCreate(SimpleCreate):
    nutrient_type_id: UUID
    # Не указана — единица берётся по правилу типа состава.
    unit_id: UUID | None = None
    # Не указан — класс берётся по типу состава.
    nutrient_class: NutrientClass | None = None


class NutrientNameUpdate(SimpleUpdate):
    nutrient_type_id: UUID | None = None
    unit_id: UUID | None = None
    nutrient_class: NutrientClass | None = None


class SimpleBulkCreate(BaseModel):
    names: list[str]
