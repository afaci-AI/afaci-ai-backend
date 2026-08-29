from uuid import UUID

from application.interfaces.product_repo import AbstractProductRepo
from domain.products.entities import Product


async def search_products(
    repo: AbstractProductRepo,
    name: str | None = None,
    region_id: UUID | None = None,
) -> list[Product]:
    return await repo.search(name=name, region_id=region_id)
