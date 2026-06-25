from uuid import UUID
from typing import Optional, List

from application.interfaces.product_repo import AbstractProductRepo
from domain.products.entities import Product


async def search_products(
    repo: AbstractProductRepo,
    name: Optional[str] = None,
    region_id: Optional[UUID] = None,
) -> List[Product]:
    return await repo.search(name=name, region_id=region_id)
