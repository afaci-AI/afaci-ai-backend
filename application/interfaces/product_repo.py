from abc import ABC, abstractmethod
from uuid import UUID

from domain.products.entities import Product


class AbstractProductRepo(ABC):
    @abstractmethod
    async def get_by_id(self, product_id: UUID) -> Product | None: ...

    @abstractmethod
    async def search(
        self,
        name: str | None = None,
        region_id: UUID | None = None,
    ) -> list[Product]: ...
