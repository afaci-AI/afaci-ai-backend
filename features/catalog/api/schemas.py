"""Схемы запросов справочников."""

from uuid import UUID

from pydantic import BaseModel


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


class NutrientNameUpdate(SimpleUpdate):
    nutrient_type_id: UUID | None = None
    unit_id: UUID | None = None


class SimpleBulkCreate(BaseModel):
    names: list[str]
