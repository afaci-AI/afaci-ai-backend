"""Плоские таблицы продуктов и нутриентов (для pandas, Excel и клиентов)."""

import io
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from ..app import TableService
from .deps import get_table_service

TAG = "Table (Flat)"

router = APIRouter(prefix="/api/v1/table", tags=[TAG])


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
    service: Annotated[TableService, Depends(get_table_service)],
    region: Annotated[
        str | None, Query(description="Фильтр по региону (часть, без учёта регистра)")
    ] = None,
    category: Annotated[
        str | None, Query(description="Фильтр по категории (часть, без учёта регистра)")
    ] = None,
    subcategory: Annotated[
        str | None,
        Query(description="Фильтр по подкатегории (часть, без учёта регистра)"),
    ] = None,
    product: Annotated[
        str | None,
        Query(description="Фильтр по названию продукта (часть, без учёта регистра)"),
    ] = None,
    nutrient_type: Annotated[
        str | None,
        Query(description="Фильтр по типу нутриента (часть, без учёта регистра)"),
    ] = None,
    nutrient_name: Annotated[
        str | None,
        Query(description="Фильтр по названию нутриента (часть, без учёта регистра)"),
    ] = None,
    sort_by: Annotated[
        str, Query(description="Колонка для сортировки")
    ] = "product_name",
    sort_order: Annotated[
        Literal["asc", "desc"], Query(description="Направление сортировки")
    ] = "asc",
    limit: Annotated[int, Query(ge=1, le=10000, description="Максимум строк")] = 1000,
    offset: Annotated[int, Query(ge=0, description="Сдвиг (пагинация)")] = 0,
):
    filters = {
        "region": region,
        "category": category,
        "subcategory": subcategory,
        "product": product,
        "nutrient_type": nutrient_type,
        "nutrient_name": nutrient_name,
    }
    return await service.nutrients(filters, sort_by, sort_order, limit, offset)


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
    service: Annotated[TableService, Depends(get_table_service)],
    region: Annotated[
        str | None, Query(description="Фильтр по региону (часть, без учёта регистра)")
    ] = None,
    category: Annotated[
        str | None, Query(description="Фильтр по категории (часть, без учёта регистра)")
    ] = None,
    subcategory: Annotated[
        str | None,
        Query(description="Фильтр по подкатегории (часть, без учёта регистра)"),
    ] = None,
    product: Annotated[
        str | None,
        Query(description="Фильтр по названию продукта (часть, без учёта регистра)"),
    ] = None,
    category_id: Annotated[
        UUID | None, Query(description="Точный фильтр по категории (ID)")
    ] = None,
    subcategory_id: Annotated[
        UUID | None, Query(description="Точный фильтр по подкатегории (ID)")
    ] = None,
    region_id: Annotated[
        UUID | None, Query(description="Точный фильтр по региону (ID)")
    ] = None,
    sort_by: Annotated[
        str, Query(description="Колонка для сортировки")
    ] = "product_name",
    sort_order: Annotated[
        Literal["asc", "desc"], Query(description="Направление сортировки")
    ] = "asc",
    limit: Annotated[int, Query(ge=1, le=10000, description="Максимум строк")] = 1000,
    offset: Annotated[int, Query(ge=0, description="Сдвиг (пагинация)")] = 0,
):
    filters = {"region": region, "category": category, "subcategory": subcategory}
    ids = {
        "p.category_id": category_id,
        "p.subcategory_id": subcategory_id,
        "p.region_id": region_id,
    }
    return await service.products(
        filters, product, ids, sort_by, sort_order, limit, offset
    )


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
    service: Annotated[TableService, Depends(get_table_service)],
    region: Annotated[
        str | None, Query(description="Фильтр по региону (часть, без учёта регистра)")
    ] = None,
    category: Annotated[
        str | None, Query(description="Фильтр по категории (часть, без учёта регистра)")
    ] = None,
    subcategory: Annotated[
        str | None,
        Query(description="Фильтр по подкатегории (часть, без учёта регистра)"),
    ] = None,
    product: Annotated[
        str | None,
        Query(description="Фильтр по названию продукта (часть, без учёта регистра)"),
    ] = None,
    nutrient_type: Annotated[
        str | None,
        Query(description="Фильтр по типу нутриента (часть, без учёта регистра)"),
    ] = None,
):
    filters = {
        "region": region,
        "category": category,
        "subcategory": subcategory,
        "product": product,
        "nutrient_type": nutrient_type,
    }
    return await service.pivot(filters)


@router.get(
    "/nutrients/map",
    summary="Нутриенты — массив продуктов, нутриенты свёрнуты в {name: quantity}",
    description=(
        "Плоский массив продуктов. Нутриенты каждого продукта свёрнуты в словарь "
        "`nutrient_name → quantity`. Готово для `pd.DataFrame(response.json())`."
    ),
)
async def table_nutrients_map(
    service: Annotated[TableService, Depends(get_table_service)],
    region: Annotated[
        str | None, Query(description="Фильтр по региону (часть, без учёта регистра)")
    ] = None,
    category: Annotated[
        str | None, Query(description="Фильтр по категории (часть, без учёта регистра)")
    ] = None,
    subcategory: Annotated[
        str | None,
        Query(description="Фильтр по подкатегории (часть, без учёта регистра)"),
    ] = None,
    product: Annotated[
        str | None,
        Query(description="Фильтр по названию продукта (часть, без учёта регистра)"),
    ] = None,
    nutrient_type: Annotated[
        str | None,
        Query(description="Фильтр по типу нутриента (часть, без учёта регистра)"),
    ] = None,
    nutrient_name: Annotated[
        str | None,
        Query(description="Фильтр по названию нутриента (часть, без учёта регистра)"),
    ] = None,
    sort_by: Annotated[
        str,
        Query(
            description="Колонка для сортировки (product_name, category_name, region_name)"
        ),
    ] = "product_name",
    sort_order: Annotated[
        Literal["asc", "desc"], Query(description="Направление сортировки")
    ] = "asc",
):
    filters = {
        "region": region,
        "category": category,
        "subcategory": subcategory,
        "product": product,
        "nutrient_type": nutrient_type,
        "nutrient_name": nutrient_name,
    }
    return await service.nutrient_map(filters, sort_by, sort_order)


@router.get(
    "/products/map",
    summary="Продукты в виде карты  category → region → [products]",
)
async def table_products_map(
    service: Annotated[TableService, Depends(get_table_service)],
    region: Annotated[
        str | None, Query(description="Фильтр по региону (часть, без учёта регистра)")
    ] = None,
    category: Annotated[
        str | None, Query(description="Фильтр по категории (часть, без учёта регистра)")
    ] = None,
    subcategory: Annotated[
        str | None,
        Query(description="Фильтр по подкатегории (часть, без учёта регистра)"),
    ] = None,
    product: Annotated[
        str | None,
        Query(description="Фильтр по названию продукта (часть, без учёта регистра)"),
    ] = None,
):
    filters = {
        "region": region,
        "category": category,
        "subcategory": subcategory,
        "product": product,
    }
    return await service.product_map(filters)


@router.get(
    "/nutrients/csv",
    summary="Нутриенты — 4 колонки (Продукт, Регион, Показатель, Значение)",
)
async def table_nutrients_csv(
    service: Annotated[TableService, Depends(get_table_service)],
    region: Annotated[
        str | None, Query(description="Фильтр по региону (часть, без учёта регистра)")
    ] = None,
    category: Annotated[
        str | None, Query(description="Фильтр по категории (часть, без учёта регистра)")
    ] = None,
    product: Annotated[
        str | None,
        Query(description="Фильтр по названию продукта (часть, без учёта регистра)"),
    ] = None,
    nutrient_type: Annotated[
        str | None,
        Query(description="Фильтр по типу нутриента (часть, без учёта регистра)"),
    ] = None,
    nutrient_name: Annotated[
        str | None,
        Query(description="Фильтр по названию нутриента (часть, без учёта регистра)"),
    ] = None,
    sort_by: Annotated[
        str, Query(description="product_name / region_name / nutrient_name / quantity")
    ] = "product_name",
    sort_order: Annotated[Literal["asc", "desc"], Query()] = "asc",
    limit: Annotated[int, Query(ge=1, le=50000)] = 10000,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    filters = {
        "region": region,
        "category": category,
        "product": product,
        "nutrient_type": nutrient_type,
        "nutrient_name": nutrient_name,
    }
    content = await service.nutrients_csv(filters, sort_by, sort_order, limit, offset)
    return StreamingResponse(
        io.BytesIO(content),
        media_type="text/csv; charset=utf-8-sig",
        headers={"Content-Disposition": "attachment; filename=nutrients.csv"},
    )
