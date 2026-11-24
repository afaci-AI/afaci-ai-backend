"""Плоские таблицы продуктов и нутриентов: проверка сортировки и форма ответа."""

from __future__ import annotations

from dataclasses import replace

from ..domain.filters import ExactIds, Page, Sorting, TableFilters
from ..domain.shapes import (
    CSV_SORT_COLUMNS,
    NUTRIENT_COLUMNS,
    PRODUCT_COLUMNS,
    nutrient_map,
    nutrients_csv,
    pivot_rows,
    product_tree,
    safe_sort,
)
from .ports import TableQueries


def _safe(sorting: Sorting, allowed: frozenset[str]) -> Sorting:
    return replace(sorting, by=safe_sort(sorting.by, allowed))


class TableService:
    def __init__(self, queries: TableQueries) -> None:
        self._queries = queries

    async def nutrients(
        self, filters: TableFilters, sorting: Sorting, page: Page
    ) -> list[dict]:
        return await self._queries.nutrients(
            filters, _safe(sorting, NUTRIENT_COLUMNS), page
        )

    async def products(
        self, filters: TableFilters, ids: ExactIds, sorting: Sorting, page: Page
    ) -> list[dict]:
        return await self._queries.products(
            filters, ids, _safe(sorting, PRODUCT_COLUMNS), page
        )

    async def pivot(self, filters: TableFilters) -> list[dict]:
        return pivot_rows(await self._queries.pivot_rows(filters))

    async def nutrient_map(self, filters: TableFilters, sorting: Sorting) -> list[dict]:
        rows = await self._queries.map_rows(filters, _safe(sorting, PRODUCT_COLUMNS))
        return nutrient_map(rows)

    async def product_map(self, filters: TableFilters) -> dict:
        return product_tree(await self._queries.product_rows(filters))

    async def nutrients_csv(
        self, filters: TableFilters, sorting: Sorting, page: Page
    ) -> bytes:
        rows = await self._queries.csv_rows(
            filters, _safe(sorting, CSV_SORT_COLUMNS), page
        )
        return nutrients_csv(rows)
