"""Сохранённая рецептура пользователя: минимальные данные для расчёта метрик и ранжирования."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID


@dataclass
class RecipeItem:
    product_id: UUID
    amount_g: float
    sort_order: int = 0
    price_per_kg: float | None = None


@dataclass
class RecipeMetrics:
    bc: float | None = None
    kras: float | None = None
    u: float | None = None
    g: float | None = None
    energy_kcal: float | None = None
    c_min_name: str | None = None
    c_min_score: float | None = None


@dataclass
class RecipeGroup:
    id: UUID
    name: str
    created_at: datetime | None = None


@dataclass
class Recipe:
    name: str
    reference_protein_id: UUID
    group_id: UUID | None = None
    id: UUID | None = None
    metrics: RecipeMetrics = field(default_factory=RecipeMetrics)
    items: list[RecipeItem] = field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None
    items_changed: bool = False

    def rename(self, name: str) -> None:
        self.name = name

    def replace_items(self, items: list[RecipeItem]) -> None:
        self.items = items
        self.items_changed = True

    def sorted_items(self) -> list[RecipeItem]:
        return sorted(self.items, key=lambda item: item.sort_order)

    def apply_metrics(self, metrics: RecipeMetrics) -> None:
        self.metrics = metrics

    def clear_metrics(self) -> None:
        """Сбросить показатели (рецептура-черновик без расчёта)."""
        self.metrics = RecipeMetrics()
