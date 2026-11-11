"""SQL-реализация порта норм и источников."""

from __future__ import annotations

from collections.abc import Mapping
from uuid import UUID

from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession

from ..domain.daily_norms import PRODUCT_NUTRIENT_BY_KEY


class SqlNormsRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def registry_sources(self) -> list[Mapping]:
        return list(
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

    async def reference_sources(self) -> list[Mapping]:
        return list(
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

    async def norms(self) -> list[dict]:
        rows = (
            (
                await self._db.execute(
                    text(
                        "SELECT key, name, unit, value, source_id, basis "
                        "FROM daily_norms ORDER BY sort_order"
                    )
                )
            )
            .mappings()
            .all()
        )
        return [{**row, "source_id": str(row["source_id"])} for row in rows]

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
