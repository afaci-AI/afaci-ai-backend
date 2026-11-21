"""Порты чтения данных для отчётов."""

from __future__ import annotations

from typing import Protocol

from .models import ListCriteria, RankingCriteria


class ReportQueries(Protocol):
    async def products(self, criteria: ListCriteria, limit: int) -> list[dict]:
        """Сырьё с белком, жиром и углеводами (None, если показателя нет)."""
        ...

    async def lookup_products(self, name: str, limit: int) -> list[dict]:
        """Подбор продукта для карточки: id, название, категория, регион."""
        ...

    async def nutrient_unit(self, name: str) -> str | None:
        """Единица нутриента или None, если такого нутриента нет."""
        ...

    async def ranking(self, criteria: RankingCriteria) -> list[dict]: ...

    async def product(self, product_id: str) -> dict | None: ...

    async def product_nutrients(self, product_id: str) -> list[dict]: ...

    async def options(self) -> dict:
        """Значения для формы: категории, подкатегории, регионы, нутриенты."""
        ...
