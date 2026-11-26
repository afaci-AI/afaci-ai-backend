"""Суточные нормы, реестр источников и доля от нормы для продукта и рецептуры."""

from __future__ import annotations

from collections.abc import Mapping
from uuid import UUID

from core.errors import NotFoundError

from ..domain.daily_norms import (
    NORMS_INFO,
    PRODUCT_NUTRIENT_BY_KEY,
    amounts_from_macros,
    build_class_rows,
    build_norm_rows,
    mineral_norm_rows,
)
from ..domain.records import CompositionEntry, Source
from ..domain.sources import merge_sources
from .ports import NormsRepository


class NormsService:
    def __init__(self, repo: NormsRepository) -> None:
        self._repo = repo

    async def sources(self) -> list[Source]:
        """Источники; ссылку на PDF строит слой api по `pdf_filename`."""
        return merge_sources(
            await self._repo.registry_sources(),
            await self._repo.reference_sources(),
        )

    async def payload(
        self,
        amounts: dict[str, float | None] | None = None,
        micro: list[CompositionEntry] | None = None,
        other: list[CompositionEntry] | None = None,
    ) -> dict:
        """
        Блоки макро-, микросостава и прочего, источники и пояснение.

        Доля от нормы считается, если переданы содержания; `norms` — прежнее имя
        списка `macro`. Без `micro` (общий список норм) микросостав — нормы
        минералов без содержания.
        """
        norms = await self._repo.norms()
        rows = build_norm_rows(norms, amounts)
        micro_rows = (
            mineral_norm_rows(norms)
            if micro is None
            else build_class_rows(micro, norms)
        )
        used = {row["source_id"] for row in rows + micro_rows if row["source_id"]}
        sources = [s for s in await self.sources() if s.id in used]
        return {
            "macro": rows,
            "norms": rows,
            "micro": micro_rows,
            "other": build_class_rows(other or []),
            "sources": sources,
            "info": NORMS_INFO,
        }

    async def recipe_payload(
        self,
        macro: Mapping[str, float | None],
        energy_kcal: float | None,
        micro: list[CompositionEntry],
        other: list[CompositionEntry],
    ) -> dict:
        """Доля от нормы для рецептуры: её сумма равна 100 г, поэтому макросостав
        калькулятора — это содержание на 100 г."""
        amounts = amounts_from_macros(
            macro.get("protein"),
            macro.get("fat"),
            macro.get("carb"),
            macro.get("fiber"),
            energy=energy_kcal,
        )
        return await self.payload(amounts, micro, other)

    async def product_payload(self, product_id: UUID) -> dict:
        by_name = await self._repo.product_macros(product_id)
        if by_name is None:
            raise NotFoundError("Product not found")
        amounts = amounts_from_macros(
            by_name.get(PRODUCT_NUTRIENT_BY_KEY["protein"]),
            by_name.get(PRODUCT_NUTRIENT_BY_KEY["fat"]),
            by_name.get(PRODUCT_NUTRIENT_BY_KEY["carbs"]),
            by_name.get(PRODUCT_NUTRIENT_BY_KEY["fiber"]),
        )
        composition = await self._repo.product_composition(product_id)
        return await self.payload(amounts, composition.micro, composition.other)
