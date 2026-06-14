from pydantic import BaseModel
from uuid import UUID
from typing import Optional, List

# Существующие схемы
class SimpleCreate(BaseModel):
    name: str

class SimpleUpdate(BaseModel):
    name: Optional[str] = None

class ProductCreate(BaseModel):
    name: str
    category_id: UUID
    subcategory_id: Optional[UUID] = None
    region_id: UUID

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    category_id: Optional[UUID] = None
    subcategory_id: Optional[UUID] = None
    region_id: Optional[UUID] = None

class NutrientCreate(BaseModel):
    product_id: UUID
    nutrient_name_id: UUID
    unit_id: UUID
    quantity: float

class NutrientUpdate(BaseModel):
    product_id: Optional[UUID] = None
    nutrient_name_id: Optional[UUID] = None
    unit_id: Optional[UUID] = None
    quantity: Optional[float] = None

# Для массового создания справочников
class SimpleBulkCreate(BaseModel):
    names: List[str]

# Для автоматического создания продукта (передаем имена, не ID)
class ProductAutoCreate(BaseModel):
    name: str
    category_name: str
    subcategory_name: Optional[str] = None
    region_name: str

# Для массового создания нутриентов
class NutrientBulkCreate(BaseModel):
    items: List[NutrientCreate]