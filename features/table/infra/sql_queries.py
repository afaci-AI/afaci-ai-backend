"""SQL плоских таблиц: выборки с разыменованием справочников и поиском по названию."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.fuzzy_search import fuzzy_matches
from core.db.text_filters import (
    contains_clause,
    fold_sql,
    parse_search_query,
    relevance_sql,
    search_match_sql,
    strip_sql,
    tokens_sql,
)

# Смысловое имя фильтра → колонка в запросе.
FILTER_COLUMNS = {
    "region": "r.name",
    "category": "c.name",
    "subcategory": "sc.name",
    "product": "p.name",
    "nutrient_type": "nt.name",
    "nutrient_name": "nn.name",
}

NUTRIENT_JOINS = """
        FROM nutrients n
        JOIN products p             ON n.id_product         = p.id
        JOIN categories c           ON p.category_id        = c.id
        LEFT JOIN subcategories sc  ON p.subcategory_id     = sc.id
        JOIN regions r              ON p.region_id          = r.id
        JOIN nutrients_names nn     ON n.id_name_component  = nn.id
        JOIN nutrients_types nt     ON n.id_type_component  = nt.id
        JOIN units u                ON n.unit_id            = u.id
"""

PRODUCT_COLUMNS_SQL = """
            p.id::text             AS product_id,
            p.name                 AS product_name,
            c.name                 AS category_name,
            sc.name                AS subcategory_name,
            r.name                 AS region_name"""


def build_where(filters: dict[str, str | None]) -> tuple[str, dict]:
    """Условия по названиям: без учёта регистра, `ё/е` и пробелов (см. text_filters).

    Значение, состоящее из одних пробелов, фильтр не включает.
    """
    clauses = []
    params: dict = {}
    for i, (name, val) in enumerate(filters.items()):
        if val is None:
            continue
        clause, clause_params = contains_clause(FILTER_COLUMNS[name], val, f"p{i}")
        if clause:
            clauses.append(clause)
            params.update(clause_params)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    return where, params


def add_exact_ids(where: str, params: dict, ids: dict[str, UUID | None]) -> str:
    """Добавляет точные условия по ID справочников (применяются до пагинации)."""
    clauses = []
    for i, (col, val) in enumerate(ids.items()):
        if val is not None:
            key = f"id{i}"
            clauses.append(f"{col} = CAST(:{key} AS uuid)")
            params[key] = str(val)
    if not clauses:
        return where
    joined = " AND ".join(clauses)
    return f"{where} AND {joined}" if where else f"WHERE {joined}"


class SqlTableQueries:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def _rows(self, sql, params: dict) -> list:
        result = await self._db.execute(sql, params)
        return list(result.mappings().all())

    async def nutrients(
        self, filters: dict, sort_by: str, sort_order: str, limit: int, offset: int
    ) -> list[dict]:
        where, params = build_where(filters)
        params["_limit"] = limit
        params["_offset"] = offset
        sql = text(f"""
        SELECT
            p.id::text             AS product_id,
            p.name                 AS product_name,
            c.name                 AS category_name,
            sc.name                AS subcategory_name,
            r.name                 AS region_name,
            nn.name                AS nutrient_name,
            nt.name                AS nutrient_type,
            u.name                 AS unit,
            n.quantity,
            n.error_rate
        {NUTRIENT_JOINS}
        {where}
        ORDER BY {sort_by} {sort_order}, p.id, n.id
        LIMIT :_limit OFFSET :_offset
    """)
        return [dict(r) for r in await self._rows(sql, params)]

    async def products(
        self,
        filters: dict,
        product: str | None,
        ids: dict[str, UUID | None],
        sort_by: str,
        sort_order: str,
        limit: int,
        offset: int,
    ) -> list[dict]:
        where, params = build_where(filters)

        # Поиск по названию: слова в любом порядке и ранжирование по релевантности.
        # Приоритет идёт перед выбранной сортировкой, внутри приоритета — сортировка.
        search = parse_search_query(product)
        lateral = ""
        relevance_order = ""
        if search:
            # Похожие названия (с опечатками) считаются в Python: в БД с локалью C
            # pg_trgm и levenshtein не работают с кириллицей (см. fuzzy_search.py).
            names = await self._db.execute(
                text("SELECT CAST(id AS text), name FROM products")
            )
            near, far = fuzzy_matches(product or "", names.all())
            folded, fold_params = fold_sql("p.name", "pf_")
            stripped, strip_params = strip_sql("pf.s", "pn_")
            tokens, token_params = tokens_sql("pf.s", "pk")
            match_clause, match_params = search_match_sql("pn.n", "pn.tk", search, "pq")
            relevance, relevance_params = relevance_sql(
                "pn.n", search, "pq", word_clause=match_clause, near_param="fz_near"
            )
            params.update(
                fold_params
                | strip_params
                | token_params
                | match_params
                | relevance_params
            )
            lateral = (
                f"CROSS JOIN LATERAL (SELECT {folded} AS s) pf "
                f"CROSS JOIN LATERAL (SELECT {stripped} AS n, {tokens} AS tk) pn"
            )
            condition = match_clause
            if near or far:
                params["fz_near"] = near
                params["fz_all"] = near + far
                condition = (
                    f"({match_clause} OR CAST(p.id AS text) = "
                    "ANY(CAST(:fz_all AS text[])))"
                )
            else:
                # Нечётких совпадений нет: список пустой, приоритеты 4–5 не нужны.
                params["fz_near"] = []
            where = f"{where} AND {condition}" if where else f"WHERE {condition}"
            relevance_order = f"{relevance}, "

        where = add_exact_ids(where, params, ids)
        params["_limit"] = limit
        params["_offset"] = offset
        sql = text(f"""
        SELECT {PRODUCT_COLUMNS_SQL}
        FROM products p
        {lateral}
        JOIN categories c           ON p.category_id    = c.id
        LEFT JOIN subcategories sc  ON p.subcategory_id = sc.id
        JOIN regions r              ON p.region_id      = r.id
        {where}
        ORDER BY {relevance_order}{sort_by} {sort_order}, p.id
        LIMIT :_limit OFFSET :_offset
    """)
        return [dict(r) for r in await self._rows(sql, params)]

    async def pivot_rows(self, filters: dict) -> list:
        where, params = build_where(filters)
        sql = text(f"""
        SELECT
            p.id::text             AS product_id,
            p.name                 AS product_name,
            c.name                 AS category_name,
            sc.name                AS subcategory_name,
            r.name                 AS region_name,
            nn.name                AS nutrient_name,
            n.quantity,
            n.error_rate
        {NUTRIENT_JOINS}
        {where}
        ORDER BY p.name, nn.name
    """)
        return await self._rows(sql, params)

    async def map_rows(self, filters: dict, sort_by: str, sort_order: str) -> list:
        where, params = build_where(filters)
        sql = text(f"""
        SELECT
            p.id::text             AS product_id,
            p.name                 AS product_name,
            c.name                 AS category_name,
            sc.name                AS subcategory_name,
            r.name                 AS region_name,
            nn.name                AS nutrient_name,
            n.quantity
        {NUTRIENT_JOINS}
        {where}
        ORDER BY {sort_by} {sort_order}, nn.name
    """)
        return await self._rows(sql, params)

    async def product_rows(self, filters: dict) -> list:
        where, params = build_where(filters)
        sql = text(f"""
        SELECT {PRODUCT_COLUMNS_SQL}
        FROM products p
        JOIN categories c           ON p.category_id    = c.id
        LEFT JOIN subcategories sc  ON p.subcategory_id = sc.id
        JOIN regions r              ON p.region_id      = r.id
        {where}
        ORDER BY c.name, r.name, p.name
    """)
        return await self._rows(sql, params)

    async def csv_rows(
        self, filters: dict, sort_by: str, sort_order: str, limit: int, offset: int
    ) -> list:
        where, params = build_where(filters)
        params["_limit"] = limit
        params["_offset"] = offset
        sql = text(f"""
        SELECT
            p.name   AS product_name,
            r.name   AS region_name,
            nn.name  AS nutrient_name,
            n.quantity
        FROM nutrients n
        JOIN products p             ON n.id_product        = p.id
        JOIN categories c           ON p.category_id       = c.id
        JOIN regions r              ON p.region_id         = r.id
        JOIN nutrients_names nn     ON n.id_name_component = nn.id
        JOIN nutrients_types nt     ON n.id_type_component = nt.id
        {where}
        ORDER BY {sort_by} {sort_order}
        LIMIT :_limit OFFSET :_offset
    """)
        return await self._rows(sql, params)
