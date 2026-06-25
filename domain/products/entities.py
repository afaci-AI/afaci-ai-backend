from dataclasses import dataclass
from uuid import UUID
from typing import Optional


@dataclass
class Product:
    id: UUID
    name: str
    category_id: UUID
    region_id: UUID
    subcategory_id: Optional[UUID] = None
