"""Порты калькулятора: что нужно use-case'ам от хранилища данных."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from ..domain import ProductNutrients, ReferenceProtein, ReferenceSource

__all__ = [
    "CompositionItemInput",
    "CostCandidateInput",
    "DailyNorms",
    "ExampleRecipe",
    "ExampleRecipeItem",
    "ProductNutrientReader",
    "ProductNutrients",
    "RecipeItemInput",
    "ReferenceCatalog",
    "ReferenceEntry",
    "ReferenceProtein",
    "ReferenceReader",
    "ReferenceSource",
    "ReferenceValue",
]


@dataclass(frozen=True, slots=True)
class RecipeItemInput:
    """Ингредиент рецептуры для расчёта: масса на 100 г смеси."""

    product_id: UUID
    amount_g: float


@dataclass(frozen=True, slots=True)
class CostCandidateInput:
    """Кандидат оптимизации цены: цена и допустимый диапазон массы."""

    product_id: UUID
    price_per_kg: float
    min_amount_g: float = 0.0
    max_amount_g: float = 100.0


@dataclass(frozen=True, slots=True)
class CompositionItemInput:
    """Ингредиент исходной рецептуры для оптимизации состава."""

    product_id: UUID
    amount_g: float
    min_amount_g: float = 0.0
    max_amount_g: float = 100.0
    price_per_kg: float | None = None


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


class DailyNorms(Protocol):
    async def for_recipe(
        self,
        *,
        macro: dict[str, float | None],
        energy_kcal: float | None,
        micro: list[dict],
        other: list[dict],
    ) -> dict:
        """Доля от суточной нормы для состава рецептуры на 100 г."""
