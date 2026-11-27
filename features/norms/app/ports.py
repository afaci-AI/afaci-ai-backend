"""Порты норм: хранилище норм и источников, хранилище PDF-документов."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol
from uuid import UUID

from ..domain.records import (
    DailyNorm,
    ProductComposition,
    ProductMacros,
    ReferenceSource,
    RegistrySource,
)


class NormsRepository(Protocol):
    async def registry_sources(self) -> list[RegistrySource]:
        """Записи таблицы `sources` по порядку показа."""

    async def reference_sources(self) -> list[ReferenceSource]:
        """Эталонные белки с заполненным источником (по году и названию)."""

    async def norms(self) -> list[DailyNorm]:
        """Суточные нормы по порядку показа."""

    async def product_macros(self, product_id: UUID) -> ProductMacros | None:
        """Макросостав продукта на 100 г либо None, если продукта нет."""

    async def product_composition(self, product_id: UUID) -> ProductComposition:
        """Микросостав и прочее продукта, по названию."""


class DocumentStorage(Protocol):
    def path(self, filename: str) -> Path | None:
        """Файл документа внутри хранилища либо None (нет, не PDF, вне корня)."""
