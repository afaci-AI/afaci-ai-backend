"""Порты калькулятора: что нужно use-case'ам от хранилища данных."""

from typing import Protocol
from uuid import UUID


class ReferenceReader(Protocol):
    async def get_reference(self, reference_id: UUID) -> dict | None:
        """Эталонный белок со значениями НАК и источником либо None."""


class ProductNutrientReader(Protocol):
    async def load_products(self, ids: list[UUID]) -> dict:
        """{product_id: {name, region, subcategory, chem, amino}} для найденных."""


class ReferenceCatalog(Protocol):
    async def list_reference_proteins(self) -> list[dict]: ...

    async def list_example_recipes(self) -> list[dict]: ...
