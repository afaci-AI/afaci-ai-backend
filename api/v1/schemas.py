from uuid import UUID

from pydantic import BaseModel, Field


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


class ProductCount(BaseModel):
    count: int = Field(ge=0, description="Общее количество продуктов питания в базе")


class NutrientCreate(BaseModel):
    product_id: UUID
    nutrient_name_id: UUID
    # Не указана — единицу назначает сервер по названию нутриента; если указана,
    # она должна совпадать с единицей названия.
    unit_id: UUID | None = None
    quantity: float
    error_rate: float | None = None


class NutrientUpdate(BaseModel):
    product_id: UUID | None = None
    nutrient_name_id: UUID | None = None
    unit_id: UUID | None = None
    quantity: float | None = None
    error_rate: float | None = None


class SimpleBulkCreate(BaseModel):
    names: list[str]


class ProductAutoCreate(BaseModel):
    name: str
    category_name: str
    subcategory_name: str | None = None
    region_name: str


class NutrientBulkCreate(BaseModel):
    items: list[NutrientCreate]
