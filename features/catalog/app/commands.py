"""Команды справочников: входные данные сценариев без привязки к формату API.

В `*Changes` поле `provided` отличает «не передано» от «передано как null».
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class NewSubcategory:
    name: str
    category_id: UUID


@dataclass(frozen=True)
class NewNutrientName:
    name: str
    nutrient_type_id: UUID
    # Не указана — единица берётся по правилу типа состава.
    unit_id: UUID | None = None
    # Не указан — класс берётся по типу состава.
    nutrient_class: str | None = None


@dataclass(frozen=True)
class SubcategoryChanges:
    name: str | None = None
    category_id: UUID | None = None
    provided: frozenset[str] = frozenset()


@dataclass(frozen=True)
class NutrientNameChanges:
    name: str | None = None
    nutrient_type_id: UUID | None = None
    unit_id: UUID | None = None
    nutrient_class: str | None = None
    provided: frozenset[str] = frozenset()
