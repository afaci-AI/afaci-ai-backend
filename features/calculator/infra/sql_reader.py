"""SQL-реализация портов калькулятора (чтение эталонов, продуктов, примеров)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession

CHEM_TYPE = "Химический состав"
AMINO_TYPE = "Аминокислотный состав"


class SqlCalculatorData:
    """Реализует ReferenceReader, ProductNutrientReader и ReferenceCatalog."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ------------------------------------------------- ReferenceReader
    async def get_reference(self, reference_id: UUID) -> dict | None:
        rp = (
            (
                await self._db.execute(
                    text(
                        "SELECT id, name, year, description, source_title, source_authors, "
                        "source_year, source_location, source_url "
                        "FROM reference_proteins WHERE id = :id"
                    ),
                    {"id": reference_id},
                )
            )
            .mappings()
            .first()
        )
        if not rp:
            return None
        vals = (
            (
                await self._db.execute(
                    text(
                        "SELECT amino_acid, value FROM reference_protein_values "
                        "WHERE reference_protein_id = :id"
                    ),
                    {"id": reference_id},
                )
            )
            .mappings()
            .all()
        )
        return {
            "id": str(rp["id"]),
            "name": rp["name"],
            "year": rp["year"],
            "description": rp["description"],
            "source": (
                {
                    "title": rp["source_title"],
                    "authors": rp["source_authors"],
                    "year": rp["source_year"],
                    "location": rp["source_location"],
                    "url": rp["source_url"],
                }
                if rp["source_title"]
                else None
            ),
            "values": {v["amino_acid"]: v["value"] for v in vals},
        }

    # ------------------------------------------ ProductNutrientReader
    async def load_products(self, ids: list[UUID]) -> dict:
        q = text("""
            SELECT p.id AS product_id, p.name, r.name AS region, s.name AS subcategory,
                   nn.name AS nutrient, nt.name AS ntype, n.quantity
            FROM products p
            JOIN regions r ON r.id = p.region_id
            LEFT JOIN subcategories s ON s.id = p.subcategory_id
            LEFT JOIN nutrients n ON n.id_product = p.id
            LEFT JOIN nutrients_names nn ON nn.id = n.id_name_component
            LEFT JOIN nutrients_types nt ON nt.id = nn.nutrient_type_id
            WHERE p.id IN :ids
        """).bindparams(bindparam("ids", expanding=True))
        rows = (await self._db.execute(q, {"ids": ids})).mappings().all()

        products: dict = {}
        for row in rows:
            pid = str(row["product_id"])
            prod = products.setdefault(
                pid,
                {
                    "product_id": pid,
                    "name": row["name"],
                    "region": row["region"],
                    "subcategory": row["subcategory"],
                    "chem": {},
                    "amino": {},
                },
            )
            if row["nutrient"] is None:
                continue
            if row["ntype"] == CHEM_TYPE:
                prod["chem"][row["nutrient"]] = row["quantity"]
            elif row["ntype"] == AMINO_TYPE:
                prod["amino"][row["nutrient"]] = row["quantity"]
        return products

    # ------------------------------------------------ ReferenceCatalog
    async def list_reference_proteins(self) -> list[dict]:
        rows = (
            (
                await self._db.execute(
                    text(
                        "SELECT id, name, year, is_default, description, "
                        "source_title, source_authors, source_year, source_location, "
                        "source_url, source_pdf_filename FROM reference_proteins "
                        "ORDER BY year"
                    )
                )
            )
            .mappings()
            .all()
        )
        result = []
        for rp in rows:
            vals = (
                (
                    await self._db.execute(
                        text(
                            "SELECT amino_acid, value, sort_order FROM reference_protein_values "
                            "WHERE reference_protein_id = :id ORDER BY sort_order"
                        ),
                        {"id": rp["id"]},
                    )
                )
                .mappings()
                .all()
            )
            source = None
            if rp["source_title"]:
                source = {
                    "title": rp["source_title"],
                    "authors": rp["source_authors"],
                    "year": rp["source_year"],
                    "location": rp["source_location"],
                    "url": rp["source_url"],
                    "pdf_filename": rp["source_pdf_filename"],
                }
            result.append(
                {
                    "id": str(rp["id"]),
                    "name": rp["name"],
                    "year": rp["year"],
                    "is_default": rp["is_default"],
                    "description": rp["description"],
                    "source": source,
                    "values": [
                        {"amino_acid": v["amino_acid"], "value": v["value"]}
                        for v in vals
                    ],
                }
            )
        return result

    async def list_example_recipes(self) -> list[dict]:
        recipes = (
            (
                await self._db.execute(
                    text(
                        "SELECT id, name, description, sample_type FROM recipes ORDER BY name"
                    )
                )
            )
            .mappings()
            .all()
        )
        result = []
        for rc in recipes:
            items = (
                (
                    await self._db.execute(
                        text("""
                    SELECT ri.product_id, ri.amount_g, ri.sort_order,
                           p.name AS product_name, r.name AS region, s.name AS subcategory
                    FROM recipe_items ri
                    JOIN products p ON p.id = ri.product_id
                    JOIN regions r ON r.id = p.region_id
                    LEFT JOIN subcategories s ON s.id = p.subcategory_id
                    WHERE ri.recipe_id = :id
                    ORDER BY ri.sort_order
                """),
                        {"id": rc["id"]},
                    )
                )
                .mappings()
                .all()
            )
            result.append(
                {
                    "id": str(rc["id"]),
                    "name": rc["name"],
                    "description": rc["description"],
                    "sample_type": rc["sample_type"],
                    "items": [
                        {
                            "product_id": str(it["product_id"]),
                            "name": it["product_name"],
                            "region": it["region"],
                            "subcategory": it["subcategory"],
                            "amount_g": it["amount_g"],
                        }
                        for it in items
                    ],
                }
            )
        return result
