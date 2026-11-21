"""Порт хранилища норм и источников."""

from collections.abc import Mapping
from typing import Protocol
from uuid import UUID


class NormsRepository(Protocol):
    async def registry_sources(self) -> list[Mapping]:
        """Записи таблицы `sources` по порядку показа."""

    async def reference_sources(self) -> list[Mapping]:
        """Эталонные белки с заполненным источником (по году и названию)."""

    async def norms(self) -> list[dict]:
        """Записи `daily_norms` (key, name, unit, value, source_id, basis, kind)."""

    async def product_macros(self, product_id: UUID) -> dict[str, float | None] | None:
        """{название нутриента: количество} либо None, если продукта нет."""

    async def product_composition(self, product_id: UUID) -> dict[str, list[dict]]:
        """Микросостав и прочее продукта: {класс: [{name, unit, amount}]} по названию."""
