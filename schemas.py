from pydantic import BaseModel
from uuid import UUID
from typing import Optional, List

# Существующие схемы
class SimpleCreate(BaseModel):
    name: str

class ProductCreate(BaseModel):
    name: str
    category_id: UUID
    subcategory_id: Optional[UUID] = None
    region_id: UUID

class NutrientCreate(BaseModel):
    id_product: UUID
    id_name_component: UUID
    id_type_component: UUID
    unit_id: UUID
    quantity: float

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