from dataclasses import dataclass
from uuid import UUID


@dataclass
class Product:
    id: UUID
    name: str
    category_id: UUID
    region_id: UUID
    subcategory_id: UUID | None = None
