"""Команды продуктов и нутриентов: входные данные сценариев без привязки к API.

В `*Changes` поле `provided` отличает «не передано» от «передано как null»;
`fields()` отдаёт только переданные поля.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class NewProduct:
    name: str
    category_id: UUID
    region_id: UUID
    subcategory_id: UUID | None = None


@dataclass(frozen=True)
class ProductChanges:
    name: str | None = None
    category_id: UUID | None = None
    subcategory_id: UUID | None = None
    region_id: UUID | None = None
    provided: frozenset[str] = frozenset()

    def fields(self) -> dict:
        return {name: getattr(self, name) for name in self.provided}


@dataclass(frozen=True)
class AutoProduct:
    """Продукт, чьи справочники заданы именами."""

    name: str
    category_name: str
    region_name: str
    subcategory_name: str | None = None


@dataclass(frozen=True)
class NewNutrient:
    product_id: UUID
    nutrient_name_id: UUID
    quantity: float
    # Не указана — единицу назначает название нутриента.
    unit_id: UUID | None = None
    error_rate: float | None = None


@dataclass(frozen=True)
class NutrientChanges:
    product_id: UUID | None = None
    nutrient_name_id: UUID | None = None
    unit_id: UUID | None = None
    quantity: float | None = None
    error_rate: float | None = None
    provided: frozenset[str] = frozenset()

    def fields(self) -> dict:
        return {name: getattr(self, name) for name in self.provided}
