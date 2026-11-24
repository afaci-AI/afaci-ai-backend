"""Порт чтения плоских таблиц: фильтры по смысловым именам, строки — mappings."""

from __future__ import annotations

from typing import Protocol

from ..domain.filters import ExactIds, Page, Sorting, TableFilters


class TableQueries(Protocol):
    async def nutrients(
        self, filters: TableFilters, sorting: Sorting, page: Page
    ) -> list[dict]: ...

    async def products(
        self, filters: TableFilters, ids: ExactIds, sorting: Sorting, page: Page
    ) -> list[dict]:
        """`filters.product` — поиск по словам с ранжированием, а не подстрока."""

    async def pivot_rows(self, filters: TableFilters) -> list: ...

    async def map_rows(self, filters: TableFilters, sorting: Sorting) -> list: ...

    async def product_rows(self, filters: TableFilters) -> list: ...

    async def csv_rows(
        self, filters: TableFilters, sorting: Sorting, page: Page
    ) -> list: ...
