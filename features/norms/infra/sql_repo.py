"""SQL-реализация порта норм и источников."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession

from ..domain.daily_norms import PRODUCT_NUTRIENT_BY_KEY
from ..domain.records import (
    CompositionEntry,
    DailyNorm,
    ProductComposition,
    ReferenceSource,
    RegistrySource,
)


class SqlNormsRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def registry_sources(self) -> list[RegistrySource]:
        rows = (
            (
                await self._db.execute(
                    text(
                        "SELECT id, kind, title, authors, year, location, url, "
                        "pdf_filename, used_for FROM sources ORDER BY sort_order, title"
                    )
                )
            )
            .mappings()
            .all()
        )
        return [RegistrySource.of(row) for row in rows]

    async def reference_sources(self) -> list[ReferenceSource]:
        rows = (
            (
                await self._db.execute(
                    text(
                        "SELECT name, source_title, source_authors, source_year, "
                        "source_location, source_url, source_pdf_filename "
                        "FROM reference_proteins WHERE source_title IS NOT NULL "
                        "ORDER BY year, name"
                    )
                )
            )
            .mappings()
            .all()
        )
        return [ReferenceSource.of(row) for row in rows]

    async def norms(self) -> list[DailyNorm]:
        rows = (
            (
                await self._db.execute(
                    text(
                        "SELECT key, name, unit, value, source_id, basis, kind "
                        "FROM daily_norms ORDER BY sort_order"
                    )
                )
            )
            .mappings()
            .all()
        )
        return [DailyNorm.of(row) for row in rows]

    async def product_macros(self, product_id: UUID) -> dict[str, float | None] | None:
        exists = await self._db.scalar(
            text("SELECT 1 FROM products WHERE id = :id"), {"id": product_id}
        )
        if not exists:
            return None
        rows = (
            (
                await self._db.execute(
                    text(
                        "SELECT nn.name AS nutrient, n.quantity "
                        "FROM nutrients n "
                        "JOIN nutrients_names nn ON nn.id = n.id_name_component "
                        "WHERE n.id_product = :id AND nn.name IN :names"
                    ).bindparams(bindparam("names", expanding=True)),
                    {"id": product_id, "names": list(PRODUCT_NUTRIENT_BY_KEY.values())},
                )
            )
            .mappings()
            .all()
        )
        return {row["nutrient"]: row["quantity"] for row in rows}

    async def product_composition(self, product_id: UUID) -> ProductComposition:
        rows = (
            (
                await self._db.execute(
                    text(
                        "SELECT nn.nutrient_class AS class, nn.name, u.name AS unit, "
                        "n.quantity AS amount "
                        "FROM nutrients n "
                        "JOIN nutrients_names nn ON nn.id = n.id_name_component "
                        "LEFT JOIN units u ON u.id = nn.unit_id "
                        "WHERE n.id_product = :id "
                        "AND nn.nutrient_class IN ('micro', 'other') "
                        "ORDER BY nn.name"
                    ),
                    {"id": product_id},
                )
            )
            .mappings()
            .all()
        )
        result = ProductComposition(micro=[], other=[])
        for row in rows:
            getattr(result, row["class"]).append(CompositionEntry.of(row))
        return result
