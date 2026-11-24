"""Фильтры плоских таблиц по смысловым именам; колонки SQL знает только infra."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True, kw_only=True)
class TableFilters:
    """Поиск по части названия, без учёта регистра; None — фильтра нет."""

    region: str | None = None
    category: str | None = None
    subcategory: str | None = None
    product: str | None = None
    nutrient_type: str | None = None
    nutrient_name: str | None = None

    def by_name(self) -> dict[str, str | None]:
        return asdict(self)


@dataclass(frozen=True, slots=True, kw_only=True)
class ExactIds:
    """Точные фильтры по идентификаторам справочников."""

    category_id: UUID | None = None
    subcategory_id: UUID | None = None
    region_id: UUID | None = None

    def by_name(self) -> dict[str, UUID | None]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class Sorting:
    by: str
    order: str


@dataclass(frozen=True, slots=True)
class Page:
    limit: int
    offset: int
