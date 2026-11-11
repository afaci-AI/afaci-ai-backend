"""Порт чтения плоских таблиц (строки — словари или mappings)."""

from typing import Protocol
from uuid import UUID


class TableQueries(Protocol):
    async def nutrients(
        self, filters: dict, sort_by: str, sort_order: str, limit: int, offset: int
    ) -> list[dict]: ...

    async def products(
        self,
        filters: dict,
        product: str | None,
        ids: dict[str, UUID | None],
        sort_by: str,
        sort_order: str,
        limit: int,
        offset: int,
    ) -> list[dict]: ...

    async def pivot_rows(self, filters: dict) -> list: ...

    async def map_rows(self, filters: dict, sort_by: str, sort_order: str) -> list: ...

    async def product_rows(self, filters: dict) -> list: ...

    async def csv_rows(
        self, filters: dict, sort_by: str, sort_order: str, limit: int, offset: int
    ) -> list: ...
