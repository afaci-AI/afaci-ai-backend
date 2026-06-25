from abc import ABC, abstractmethod
from uuid import UUID
from typing import Optional, List

from domain.products.entities import Product


class AbstractProductRepo(ABC):
    @abstractmethod
    async def get_by_id(self, product_id: UUID) -> Optional[Product]:
        ...

    @abstractmethod
    async def search(
        self,
        name: Optional[str] = None,
        region_id: Optional[UUID] = None,
    ) -> List[Product]:
        ...
