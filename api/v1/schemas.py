from uuid import UUID

from pydantic import BaseModel


class SimpleCreate(BaseModel):
    name: str


class SimpleUpdate(BaseModel):
    name: str | None = None


class ProductCreate(BaseModel):
    name: str
    category_id: UUID
    subcategory_id: UUID | None = None
    region_id: UUID


class ProductUpdate(BaseModel):
    name: str | None = None
    category_id: UUID | None = None
    subcategory_id: UUID | None = None
    region_id: UUID | None = None


class NutrientCreate(BaseModel):
    product_id: UUID
    nutrient_name_id: UUID
    unit_id: UUID
    quantity: float


class NutrientUpdate(BaseModel):
    product_id: UUID | None = None
    nutrient_name_id: UUID | None = None
    unit_id: UUID | None = None
    quantity: float | None = None


class SimpleBulkCreate(BaseModel):
    names: list[str]


class ProductAutoCreate(BaseModel):
    name: str
    category_name: str
    subcategory_name: str | None = None
    region_name: str


class NutrientBulkCreate(BaseModel):
    items: list[NutrientCreate]
