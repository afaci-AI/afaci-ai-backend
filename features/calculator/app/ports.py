"""Порты калькулятора: что нужно use-case'ам от хранилища данных."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from ..domain import ProductNutrients, ReferenceProtein, ReferenceSource

__all__ = [
    "ExampleRecipe",
    "ExampleRecipeItem",
    "ProductNutrientReader",
    "ProductNutrients",
    "ReferenceCatalog",
    "ReferenceEntry",
    "ReferenceProtein",
    "ReferenceReader",
    "ReferenceSource",
    "ReferenceValue",
]


@dataclass(frozen=True, slots=True)
class ReferenceValue:
    amino_acid: str
    value: float


@dataclass(frozen=True, slots=True)
class ReferenceEntry:
    """Эталон для справочника: значения в порядке таблицы, имя файла источника."""

    id: str
    name: str
    year: int | None
    is_default: bool
    description: str | None
    source: ReferenceSource | None
    source_pdf_filename: str | None
    values: list[ReferenceValue]


@dataclass(frozen=True, slots=True)
class ExampleRecipeItem:
    product_id: str
    name: str
    region: str | None
    subcategory: str | None
    amount_g: float


@dataclass(frozen=True, slots=True)
class ExampleRecipe:
    id: str
    name: str
    description: str | None
    sample_type: str | None
    items: list[ExampleRecipeItem]


class ReferenceReader(Protocol):
    async def get_reference(self, reference_id: UUID) -> ReferenceProtein | None:
        """Эталонный белок со значениями НАК и источником либо None."""


class ProductNutrientReader(Protocol):
    async def load_products(self, ids: list[UUID]) -> dict[str, ProductNutrients]:
        """Найденные продукты по строковому id; ненайденных в ответе нет."""


class ReferenceCatalog(Protocol):
    async def list_reference_proteins(self) -> list[ReferenceEntry]: ...

    async def list_example_recipes(self) -> list[ExampleRecipe]: ...
