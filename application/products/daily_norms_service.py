"""
Суточные нормы, реестр источников и доля от нормы для продукта и рецептуры.

Чтение справочников `daily_norms` и `sources` и сборка ответа API поверх чистой
логики `domain.products.daily_norms`. Нормы и доля считаются здесь, на backend:
клиенты только показывают готовые значения.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from domain.products.daily_norms import (
    NORMS_INFO,
    PRODUCT_NUTRIENT_BY_KEY,
    amounts_from_macros,
    build_norm_rows,
)

PdfUrl = Callable[[str | None], str | None]

# Пространство имён для стабильных идентификаторов источников эталонных белков.
_REFERENCE_SOURCE_NS = uuid.UUID("8c1d3a52-6e4f-4b7a-9d20-3f5a1c7e9b01")
_REFERENCE_SORT_BASE = 100


def _source_row(row, pdf_url: PdfUrl) -> dict:
    return {
        "id": str(row["id"]),
        "kind": row["kind"],
        "title": row["title"],
        "authors": row["authors"],
        "year": row["year"],
        "location": row["location"],
        "url": row["url"],
        "pdf_url": pdf_url(row["pdf_filename"]),
        "used_for": row["used_for"],
    }


async def load_sources(db: AsyncSession, pdf_url: PdfUrl) -> list[dict]:
    """
    Реестр источников: записи `sources` и источники эталонов ФАО/ВОЗ.

    Источники эталонов остаются в `reference_proteins` (единое место правды) и
    добавляются к реестру при чтении; совпадающие записи (один документ у
    нескольких эталонов) объединяются, в «Где применяется» перечисляются эталоны.
    """
    result = [
        _source_row(row, pdf_url)
        for row in (
            await db.execute(
                text(
                    "SELECT id, kind, title, authors, year, location, url, "
                    "pdf_filename, used_for FROM sources ORDER BY sort_order, title"
                )
            )
        )
        .mappings()
        .all()
    ]
    references = (
        (
            await db.execute(
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
    merged: dict[tuple, dict] = {}
    for ref in references:
        key = (ref["source_title"], ref["source_year"], ref["source_url"])
        entry = merged.get(key)
        if entry is None:
            authors = ref["source_authors"] or ""
            entry = {
                "id": str(uuid.uuid5(_REFERENCE_SOURCE_NS, "|".join(map(str, key)))),
                "kind": "article" if "Journal" in authors else "document",
                "title": ref["source_title"],
                "authors": ref["source_authors"],
                "year": ref["source_year"],
                "location": ref["source_location"],
                "url": ref["source_url"],
                "pdf_url": pdf_url(ref["source_pdf_filename"]),
                "used_for": None,
                "_names": [],
            }
            merged[key] = entry
        entry["_names"].append(ref["name"])
    for entry in merged.values():
        names = entry.pop("_names")
        entry["used_for"] = "Эталонный белок: " + ", ".join(names)
        result.append(entry)
    return result


async def load_norms(db: AsyncSession) -> list[dict]:
    rows = (
        (
            await db.execute(
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


async def product_amounts(
    db: AsyncSession, product_id: UUID
) -> dict[str, float | None] | None:
    """Содержание на 100 г продукта по ключам норм или None, если продукта нет."""
    exists = await db.scalar(
        text("SELECT 1 FROM products WHERE id = :id"), {"id": product_id}
    )
    if not exists:
        return None
    rows = (
        (
            await db.execute(
                text(
                    "SELECT nn.name AS nutrient, n.quantity "
                    "FROM nutrients n "
                    "JOIN nutrients_names nn ON nn.id = n.id_name_component "
                    "WHERE n.id_product = :id AND nn.name IN :names"
                ).bindparams(_names_param()),
                {"id": product_id, "names": list(PRODUCT_NUTRIENT_BY_KEY.values())},
            )
        )
        .mappings()
        .all()
    )
    by_name = {row["nutrient"]: row["quantity"] for row in rows}
    return amounts_from_macros(
        by_name.get(PRODUCT_NUTRIENT_BY_KEY["protein"]),
        by_name.get(PRODUCT_NUTRIENT_BY_KEY["fat"]),
        by_name.get(PRODUCT_NUTRIENT_BY_KEY["carbs"]),
        by_name.get(PRODUCT_NUTRIENT_BY_KEY["fiber"]),
    )


def _names_param():
    from sqlalchemy import bindparam

    return bindparam("names", expanding=True)


async def daily_norms_payload(
    db: AsyncSession,
    pdf_url: PdfUrl,
    amounts: dict[str, float | None] | None = None,
) -> dict:
    """Нормы, доля от нормы (если переданы содержания), источники и пояснение."""
    norms = await load_norms(db)
    rows = build_norm_rows(norms, amounts)
    used = {row["source_id"] for row in rows}
    sources = [s for s in await load_sources(db, pdf_url) if s["id"] in used]
    return {"norms": rows, "sources": sources, "info": NORMS_INFO}
