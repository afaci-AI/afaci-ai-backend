"""Только чтение: SQL-выборки для отчётов по таблицам из core/db/models."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.text_filters import contains_clause
from features.calculator.domain.formulas.constants import CARB, FAT, PROTEIN

from ..app.models import ListCriteria, RankingCriteria

PRODUCT_JOINS = """
        FROM products p
        JOIN categories c          ON p.category_id    = c.id
        LEFT JOIN subcategories sc ON p.subcategory_id = sc.id
        JOIN regions r             ON p.region_id      = r.id
"""


def _conditions(pairs: list[tuple[str, str | None]]) -> tuple[list[str], dict]:
    clauses: list[str] = []
    params: dict = {}
    for i, (column, value) in enumerate(pairs):
        if value is None:
            continue
        clause, clause_params = contains_clause(column, value, f"f{i}")
        if clause:
            clauses.append(clause)
            params.update(clause_params)
    return clauses, params


class SqlReportQueries:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def _rows(self, sql, params: dict) -> list[dict]:
        result = await self._db.execute(sql, params)
        return [dict(r) for r in result.mappings().all()]

    async def products(self, criteria: ListCriteria, limit: int) -> list[dict]:
        clauses, params = _conditions(
            [
                ("c.name", criteria.category),
                ("sc.name", criteria.subcategory),
                ("r.name", criteria.region),
                ("p.name", criteria.name),
            ]
        )
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        params.update(protein=PROTEIN, fat=FAT, carb=CARB, limit=limit)
        sql = text(f"""
        SELECT p.id::text AS id, p.name, r.name AS region,
               MAX(n.quantity) FILTER (WHERE nn.name = :protein) AS protein,
               MAX(n.quantity) FILTER (WHERE nn.name = :fat)     AS fat,
               MAX(n.quantity) FILTER (WHERE nn.name = :carb)    AS carb
        {PRODUCT_JOINS}
        LEFT JOIN nutrients n        ON n.id_product        = p.id
        LEFT JOIN nutrients_names nn ON n.id_name_component = nn.id
        {where}
        GROUP BY p.id, p.name, r.name
        ORDER BY p.name, p.id
        LIMIT :limit
        """)
        return await self._rows(sql, params)

    async def lookup_products(self, name: str, limit: int) -> list[dict]:
        clauses, params = _conditions([("p.name", name)])
        if not clauses:
            return []
        params["limit"] = limit
        sql = text(f"""
        SELECT p.id::text AS id, p.name, c.name AS category, r.name AS region
        {PRODUCT_JOINS}
        WHERE {" AND ".join(clauses)}
        ORDER BY p.name, r.name, p.id
        LIMIT :limit
        """)
        return await self._rows(sql, params)

    async def nutrient_unit(self, name: str) -> str | None:
        sql = text("""
        SELECT u.name FROM nutrients n
        JOIN nutrients_names nn ON n.id_name_component = nn.id
        JOIN units u            ON n.unit_id = u.id
        WHERE nn.name = :name LIMIT 1
        """)
        row = (await self._db.execute(sql, {"name": name})).first()
        return row[0] if row else None

    async def ranking(self, criteria: RankingCriteria) -> list[dict]:
        clauses, params = _conditions([("c.name", criteria.category)])
        clauses.append("nn.name = :nutrient")
        params.update(nutrient=criteria.nutrient, top=criteria.top)
        direction = "ASC" if criteria.order == "asc" else "DESC"
        sql = text(f"""
        SELECT p.id::text AS id, p.name, c.name AS category, r.name AS region,
               n.quantity, n.error_rate
        {PRODUCT_JOINS}
        JOIN nutrients n        ON n.id_product        = p.id
        JOIN nutrients_names nn ON n.id_name_component = nn.id
        WHERE {" AND ".join(clauses)}
        ORDER BY n.quantity {direction}, p.name, p.id
        LIMIT :top
        """)
        return await self._rows(sql, params)

    async def product(self, product_id: str) -> dict | None:
        sql = text(f"""
        SELECT p.id::text AS id, p.name, c.name AS category,
               sc.name AS subcategory, r.name AS region
        {PRODUCT_JOINS}
        WHERE p.id = CAST(:id AS uuid)
        """)
        rows = await self._rows(sql, {"id": product_id})
        return rows[0] if rows else None

    async def product_nutrients(self, product_id: str) -> list[dict]:
        sql = text("""
        SELECT nt.name AS type, nn.name AS name, u.name AS unit,
               n.quantity, n.error_rate
        FROM nutrients n
        JOIN nutrients_names nn ON n.id_name_component = nn.id
        JOIN nutrients_types nt ON n.id_type_component = nt.id
        JOIN units u            ON n.unit_id = u.id
        WHERE n.id_product = CAST(:id AS uuid)
        ORDER BY nt.name, nn.name
        """)
        return await self._rows(sql, {"id": product_id})

    async def options(self) -> dict:
        async def names(table: str) -> list[str]:
            rows = await self._db.execute(
                text(f"SELECT name FROM {table} ORDER BY name")
            )
            return [r[0].strip() for r in rows]

        sub_rows = await self._db.execute(
            text(
                """
            SELECT sc.name, c.name
            FROM subcategories sc JOIN categories c ON sc.category_id = c.id
            ORDER BY sc.name, c.name
            """
            )
        )
        subcategories = [
            {"name": n.strip(), "category": c.strip()} for n, c in sub_rows
        ]
        nutrient_rows = await self._db.execute(
            text("""
            SELECT DISTINCT nt.name, nn.name, u.name
            FROM nutrients n
            JOIN nutrients_names nn ON n.id_name_component = nn.id
            JOIN nutrients_types nt ON n.id_type_component = nt.id
            JOIN units u            ON n.unit_id = u.id
            ORDER BY nt.name, nn.name
            """)
        )
        return {
            "categories": await names("categories"),
            "subcategories": subcategories,
            "regions": await names("regions"),
            "nutrients": [
                {"type": t.strip(), "name": n.strip(), "unit": u.strip()}
                for t, n, u in nutrient_rows
            ],
        }
