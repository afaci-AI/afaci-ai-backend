import csv
import io
from typing import Optional, Literal
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from infrastructure.db.session import get_db

TAG = "Table (Flat)"

router = APIRouter(prefix="/api/v1/table", tags=[TAG])

_NUTRIENT_COLS = {
    "product_name", "category_name", "subcategory_name", "region_name",
    "nutrient_name", "nutrient_type", "unit", "quantity", "error_rate",
}

_PRODUCT_COLS = {
    "product_name", "category_name", "subcategory_name", "region_name",
}


@router.get(
    "/nutrients",
    summary="Плоская таблица нутриентов",
    description=(
        "Возвращает полную таблицу нутриентов с разыменованием всех FK. "
        "Готово для `pd.DataFrame(response.json())`.\n\n"
        "**Колонки:** `product_id`, `product_name`, `category_name`, "
        "`subcategory_name`, `region_name`, `nutrient_name`, `nutrient_type`, "
        "`unit`, `quantity`, `error_rate`"
    ),
)
async def table_nutrients(
    region: Optional[str] = Query(None, description="Фильтр по региону (ILIKE)"),
    category: Optional[str] = Query(None, description="Фильтр по категории (ILIKE)"),
    subcategory: Optional[str] = Query(None, description="Фильтр по подкатегории (ILIKE)"),
    product: Optional[str] = Query(None, description="Фильтр по названию продукта (ILIKE)"),
    nutrient_type: Optional[str] = Query(None, description="Фильтр по типу нутриента (ILIKE)"),
    nutrient_name: Optional[str] = Query(None, description="Фильтр по названию нутриента (ILIKE)"),
    sort_by: str = Query("product_name", description="Колонка для сортировки"),
    sort_order: Literal["asc", "desc"] = Query("asc", description="Направление сортировки"),
    limit: int = Query(1000, ge=1, le=10000, description="Максимум строк"),
    offset: int = Query(0, ge=0, description="Сдвиг (пагинация)"),
    db: AsyncSession = Depends(get_db),
):
    if sort_by not in _NUTRIENT_COLS:
        sort_by = "product_name"

    where, params = _build_where({
        "r.name": region,
        "c.name": category,
        "sc.name": subcategory,
        "p.name": product,
        "nt.name": nutrient_type,
        "nn.name": nutrient_name,
    })

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
        FROM nutrients n
        JOIN products p             ON n.id_product         = p.id
        JOIN categories c           ON p.category_id        = c.id
        LEFT JOIN subcategories sc  ON p.subcategory_id     = sc.id
        JOIN regions r              ON p.region_id          = r.id
        JOIN nutrients_names nn     ON n.id_name_component  = nn.id
        JOIN nutrients_types nt     ON n.id_type_component  = nt.id
        JOIN units u                ON n.unit_id            = u.id
        {where}
        ORDER BY {sort_by} {sort_order}
        LIMIT :_limit OFFSET :_offset
    """)

    result = await db.execute(sql, params)
    return [dict(r) for r in result.mappings().all()]


@router.get(
    "/products",
    summary="Плоская таблица продуктов",
    description=(
        "Возвращает список продуктов с разыменованием FK (category, subcategory, region). "
        "Готово для `pd.DataFrame(response.json())`.\n\n"
        "**Колонки:** `product_id`, `product_name`, `category_name`, "
        "`subcategory_name`, `region_name`"
    ),
)
async def table_products(
    region: Optional[str] = Query(None, description="Фильтр по региону (ILIKE)"),
    category: Optional[str] = Query(None, description="Фильтр по категории (ILIKE)"),
    subcategory: Optional[str] = Query(None, description="Фильтр по подкатегории (ILIKE)"),
    product: Optional[str] = Query(None, description="Фильтр по названию продукта (ILIKE)"),
    sort_by: str = Query("product_name", description="Колонка для сортировки"),
    sort_order: Literal["asc", "desc"] = Query("asc", description="Направление сортировки"),
    limit: int = Query(1000, ge=1, le=10000, description="Максимум строк"),
    offset: int = Query(0, ge=0, description="Сдвиг (пагинация)"),
    db: AsyncSession = Depends(get_db),
):
    if sort_by not in _PRODUCT_COLS:
        sort_by = "product_name"

    where, params = _build_where({
        "r.name": region,
        "c.name": category,
        "sc.name": subcategory,
        "p.name": product,
    })

    params["_limit"] = limit
    params["_offset"] = offset

    sql = text(f"""
        SELECT
            p.id::text             AS product_id,
            p.name                 AS product_name,
            c.name                 AS category_name,
            sc.name                AS subcategory_name,
            r.name                 AS region_name
        FROM products p
        JOIN categories c           ON p.category_id    = c.id
        LEFT JOIN subcategories sc  ON p.subcategory_id = sc.id
        JOIN regions r              ON p.region_id      = r.id
        {where}
        ORDER BY {sort_by} {sort_order}
        LIMIT :_limit OFFSET :_offset
    """)

    result = await db.execute(sql, params)
    return [dict(r) for r in result.mappings().all()]


@router.get(
    "/nutrients/pivot",
    summary="Пивот-таблица нутриентов (продукты × нутриенты)",
    description=(
        "Каждый продукт — одна строка. Нутриенты разворачиваются в колонки. "
        "Удобно когда нужен широкий DataFrame без группировки по строкам.\n\n"
        "Фильтры те же что у `/table/nutrients`."
    ),
)
async def table_nutrients_pivot(
    region: Optional[str] = Query(None, description="Фильтр по региону (ILIKE)"),
    category: Optional[str] = Query(None, description="Фильтр по категории (ILIKE)"),
    subcategory: Optional[str] = Query(None, description="Фильтр по подкатегории (ILIKE)"),
    product: Optional[str] = Query(None, description="Фильтр по названию продукта (ILIKE)"),
    nutrient_type: Optional[str] = Query(None, description="Фильтр по типу нутриента (ILIKE)"),
    db: AsyncSession = Depends(get_db),
):
    where, params = _build_where({
        "r.name": region,
        "c.name": category,
        "sc.name": subcategory,
        "p.name": product,
        "nt.name": nutrient_type,
    })

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
        FROM nutrients n
        JOIN products p             ON n.id_product         = p.id
        JOIN categories c           ON p.category_id        = c.id
        LEFT JOIN subcategories sc  ON p.subcategory_id     = sc.id
        JOIN regions r              ON p.region_id          = r.id
        JOIN nutrients_names nn     ON n.id_name_component  = nn.id
        JOIN nutrients_types nt     ON n.id_type_component  = nt.id
        JOIN units u                ON n.unit_id            = u.id
        {where}
        ORDER BY p.name, nn.name
    """)

    result = await db.execute(sql, params)
    rows = result.mappings().all()

    pivot: dict[str, dict] = {}
    for r in rows:
        key = r["product_id"]
        if key not in pivot:
            pivot[key] = {
                "product_id": r["product_id"],
                "product_name": r["product_name"],
                "category_name": r["category_name"],
                "subcategory_name": r["subcategory_name"],
                "region_name": r["region_name"],
            }
        col = r["nutrient_name"]
        pivot[key][col] = r["quantity"]
        if r["error_rate"] is not None:
            pivot[key][f"{col}_err"] = r["error_rate"]

    return list(pivot.values())


@router.get(
    "/nutrients/map",
    summary="Нутриенты — массив продуктов, нутриенты свёрнуты в {name: quantity}",
    description=(
        "Плоский массив продуктов. Нутриенты каждого продукта свёрнуты в словарь "
        "`nutrient_name → quantity`. Готово для `pd.DataFrame(response.json())`."
    ),
)
async def table_nutrients_map(
    region: Optional[str] = Query(None, description="Фильтр по региону (ILIKE)"),
    category: Optional[str] = Query(None, description="Фильтр по категории (ILIKE)"),
    subcategory: Optional[str] = Query(None, description="Фильтр по подкатегории (ILIKE)"),
    product: Optional[str] = Query(None, description="Фильтр по названию продукта (ILIKE)"),
    nutrient_type: Optional[str] = Query(None, description="Фильтр по типу нутриента (ILIKE)"),
    nutrient_name: Optional[str] = Query(None, description="Фильтр по названию нутриента (ILIKE)"),
    sort_by: str = Query("product_name", description="Колонка для сортировки (product_name, category_name, region_name)"),
    sort_order: Literal["asc", "desc"] = Query("asc", description="Направление сортировки"),
    db: AsyncSession = Depends(get_db),
):
    if sort_by not in _PRODUCT_COLS:
        sort_by = "product_name"

    where, params = _build_where({
        "r.name": region,
        "c.name": category,
        "sc.name": subcategory,
        "p.name": product,
        "nt.name": nutrient_type,
        "nn.name": nutrient_name,
    })

    sql = text(f"""
        SELECT
            p.id::text             AS product_id,
            p.name                 AS product_name,
            c.name                 AS category_name,
            sc.name                AS subcategory_name,
            r.name                 AS region_name,
            nn.name                AS nutrient_name,
            n.quantity
        FROM nutrients n
        JOIN products p             ON n.id_product         = p.id
        JOIN categories c           ON p.category_id        = c.id
        LEFT JOIN subcategories sc  ON p.subcategory_id     = sc.id
        JOIN regions r              ON p.region_id          = r.id
        JOIN nutrients_names nn     ON n.id_name_component  = nn.id
        JOIN nutrients_types nt     ON n.id_type_component  = nt.id
        JOIN units u                ON n.unit_id            = u.id
        {where}
        ORDER BY {sort_by} {sort_order}, nn.name
    """)

    result = await db.execute(sql, params)
    rows = result.mappings().all()

    index: dict[str, dict] = {}
    order: list[str] = []
    for r in rows:
        pid = r["product_id"]
        if pid not in index:
            index[pid] = {
                "product_id": pid,
                "product_name": r["product_name"],
                "category_name": r["category_name"],
                "subcategory_name": r["subcategory_name"],
                "region_name": r["region_name"],
                "nutrients": {},
            }
            order.append(pid)
        index[pid]["nutrients"][r["nutrient_name"]] = r["quantity"]

    return [index[pid] for pid in order]


@router.get(
    "/products/map",
    summary="Продукты в виде карты  category → region → [products]",
)
async def table_products_map(
    region: Optional[str] = Query(None, description="Фильтр по региону (ILIKE)"),
    category: Optional[str] = Query(None, description="Фильтр по категории (ILIKE)"),
    subcategory: Optional[str] = Query(None, description="Фильтр по подкатегории (ILIKE)"),
    product: Optional[str] = Query(None, description="Фильтр по названию продукта (ILIKE)"),
    db: AsyncSession = Depends(get_db),
):
    where, params = _build_where({
        "r.name": region,
        "c.name": category,
        "sc.name": subcategory,
        "p.name": product,
    })

    sql = text(f"""
        SELECT
            p.id::text             AS product_id,
            p.name                 AS product_name,
            c.name                 AS category_name,
            sc.name                AS subcategory_name,
            r.name                 AS region_name
        FROM products p
        JOIN categories c           ON p.category_id    = c.id
        LEFT JOIN subcategories sc  ON p.subcategory_id = sc.id
        JOIN regions r              ON p.region_id      = r.id
        {where}
        ORDER BY c.name, r.name, p.name
    """)

    result = await db.execute(sql, params)
    rows = result.mappings().all()

    out: dict = {}
    for r in rows:
        cat = r["category_name"]
        reg = r["region_name"]
        if cat not in out:
            out[cat] = {}
        if reg not in out[cat]:
            out[cat][reg] = []
        out[cat][reg].append({
            "product_id": r["product_id"],
            "product_name": r["product_name"],
            "subcategory_name": r["subcategory_name"],
        })

    return out


@router.get(
    "/nutrients/csv",
    summary="Нутриенты — 4 колонки (Продукт, Регион, Показатель, Значение)",
)
async def table_nutrients_csv(
    region: Optional[str] = Query(None, description="Фильтр по региону (ILIKE)"),
    category: Optional[str] = Query(None, description="Фильтр по категории (ILIKE)"),
    product: Optional[str] = Query(None, description="Фильтр по названию продукта (ILIKE)"),
    nutrient_type: Optional[str] = Query(None, description="Фильтр по типу нутриента (ILIKE)"),
    nutrient_name: Optional[str] = Query(None, description="Фильтр по названию нутриента (ILIKE)"),
    sort_by: str = Query("product_name", description="product_name / region_name / nutrient_name / quantity"),
    sort_order: Literal["asc", "desc"] = Query("asc"),
    limit: int = Query(10000, ge=1, le=50000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    allowed = {"product_name", "region_name", "nutrient_name", "quantity"}
    if sort_by not in allowed:
        sort_by = "product_name"

    where, params = _build_where({
        "r.name": region,
        "c.name": category,
        "p.name": product,
        "nt.name": nutrient_type,
        "nn.name": nutrient_name,
    })

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

    result = await db.execute(sql, params)
    rows = result.mappings().all()

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=["product_name", "region_name", "nutrient_name", "quantity"])
    writer.writeheader()
    writer.writerows([dict(r) for r in rows])

    # utf-8-sig кодирует с BOM — Excel и редакторы корректно читают кириллицу
    content = io.BytesIO(buf.getvalue().encode('utf-8-sig'))

    return StreamingResponse(
        content,
        media_type="text/csv; charset=utf-8-sig",
        headers={"Content-Disposition": "attachment; filename=nutrients.csv"},
    )


def _build_where(filters: dict[str, Optional[str]]) -> tuple[str, dict]:
    clauses = []
    params: dict = {}
    for i, (col, val) in enumerate(filters.items()):
        if val is not None:
            key = f"p{i}"
            clauses.append(f"{col} ILIKE :{key}")
            params[key] = f"%{val}%"
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    return where, params
