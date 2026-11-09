"""Плоские таблицы продуктов и нутриентов: проверка сортировки и форма ответа."""

from __future__ import annotations

from uuid import UUID

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


class TableService:
    def __init__(self, queries: TableQueries) -> None:
        self._queries = queries

    async def nutrients(
        self, filters: dict, sort_by: str, sort_order: str, limit: int, offset: int
    ) -> list[dict]:
        sort_by = safe_sort(sort_by, NUTRIENT_COLUMNS)
        return await self._queries.nutrients(
            filters, sort_by, sort_order, limit, offset
        )

    async def products(
        self,
        filters: dict,
        product: str | None,
        ids: dict[str, UUID | None],
        sort_by: str,
        sort_order: str,
        limit: int,
        offset: int,
    ) -> list[dict]:
        sort_by = safe_sort(sort_by, PRODUCT_COLUMNS)
        return await self._queries.products(
            filters, product, ids, sort_by, sort_order, limit, offset
        )

    async def pivot(self, filters: dict) -> list[dict]:
        return pivot_rows(await self._queries.pivot_rows(filters))

    async def nutrient_map(
        self, filters: dict, sort_by: str, sort_order: str
    ) -> list[dict]:
        sort_by = safe_sort(sort_by, PRODUCT_COLUMNS)
        return nutrient_map(await self._queries.map_rows(filters, sort_by, sort_order))

    async def product_map(self, filters: dict) -> dict:
        return product_tree(await self._queries.product_rows(filters))

    async def nutrients_csv(
        self, filters: dict, sort_by: str, sort_order: str, limit: int, offset: int
    ) -> bytes:
        sort_by = safe_sort(sort_by, CSV_SORT_COLUMNS)
        rows = await self._queries.csv_rows(filters, sort_by, sort_order, limit, offset)
        return nutrients_csv(rows)
