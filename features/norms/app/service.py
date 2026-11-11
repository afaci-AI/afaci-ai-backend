"""Суточные нормы, реестр источников и доля от нормы для продукта и рецептуры."""

from __future__ import annotations

from uuid import UUID

from core.errors import NotFoundError

from ..domain.daily_norms import (
    NORMS_INFO,
    PRODUCT_NUTRIENT_BY_KEY,
    PdfUrl,
    amounts_from_macros,
    build_norm_rows,
)
from ..domain.sources import merge_sources
from .ports import NormsRepository


class NormsService:
    def __init__(self, repo: NormsRepository) -> None:
        self._repo = repo

    async def sources(self, pdf_url: PdfUrl) -> list[dict]:
        return merge_sources(
            await self._repo.registry_sources(),
            await self._repo.reference_sources(),
            pdf_url,
        )

    async def payload(
        self, pdf_url: PdfUrl, amounts: dict[str, float | None] | None = None
    ) -> dict:
        """Нормы, доля от нормы (если переданы содержания), источники и пояснение."""
        rows = build_norm_rows(await self._repo.norms(), amounts)
        used = {row["source_id"] for row in rows}
        sources = [s for s in await self.sources(pdf_url) if s["id"] in used]
        return {"norms": rows, "sources": sources, "info": NORMS_INFO}

    async def product_payload(self, product_id: UUID, pdf_url: PdfUrl) -> dict:
        by_name = await self._repo.product_macros(product_id)
        if by_name is None:
            raise NotFoundError("Product not found")
        amounts = amounts_from_macros(
            by_name.get(PRODUCT_NUTRIENT_BY_KEY["protein"]),
            by_name.get(PRODUCT_NUTRIENT_BY_KEY["fat"]),
            by_name.get(PRODUCT_NUTRIENT_BY_KEY["carbs"]),
            by_name.get(PRODUCT_NUTRIENT_BY_KEY["fiber"]),
        )
        return await self.payload(pdf_url, amounts)
