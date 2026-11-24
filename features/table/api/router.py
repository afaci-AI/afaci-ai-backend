"""Плоские таблицы продуктов и нутриентов (для pandas, Excel и клиентов)."""

import io
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from ..app import TableService
from ..domain.filters import ExactIds, Page, Sorting, TableFilters
from .deps import get_table_service
from .filters import (
    csv_filters,
    csv_page,
    csv_sorting,
    exact_ids,
    map_sorting,
    nutrient_filters,
    pivot_filters,
    product_filters,
    table_page,
    table_sorting,
)

TAG = "Table (Flat)"

router = APIRouter(prefix="/api/v1/table", tags=[TAG])

Service = Annotated[TableService, Depends(get_table_service)]


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
    service: Service,
    filters: Annotated[TableFilters, Depends(nutrient_filters)],
    sorting: Annotated[Sorting, Depends(table_sorting)],
    page: Annotated[Page, Depends(table_page)],
):
    return await service.nutrients(filters, sorting, page)


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
    service: Service,
    filters: Annotated[TableFilters, Depends(product_filters)],
    ids: Annotated[ExactIds, Depends(exact_ids)],
    sorting: Annotated[Sorting, Depends(table_sorting)],
    page: Annotated[Page, Depends(table_page)],
):
    return await service.products(filters, ids, sorting, page)


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
    service: Service,
    filters: Annotated[TableFilters, Depends(pivot_filters)],
):
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
    service: Service,
    filters: Annotated[TableFilters, Depends(nutrient_filters)],
    sorting: Annotated[Sorting, Depends(map_sorting)],
):
    return await service.nutrient_map(filters, sorting)


@router.get(
    "/products/map",
    summary="Продукты в виде карты  category → region → [products]",
)
async def table_products_map(
    service: Service,
    filters: Annotated[TableFilters, Depends(product_filters)],
):
    return await service.product_map(filters)


@router.get(
    "/nutrients/csv",
    summary="Нутриенты — 4 колонки (Продукт, Регион, Показатель, Значение)",
)
async def table_nutrients_csv(
    service: Service,
    filters: Annotated[TableFilters, Depends(csv_filters)],
    sorting: Annotated[Sorting, Depends(csv_sorting)],
    page: Annotated[Page, Depends(csv_page)],
):
    content = await service.nutrients_csv(filters, sorting, page)
    return StreamingResponse(
        io.BytesIO(content),
        media_type="text/csv; charset=utf-8-sig",
        headers={"Content-Disposition": "attachment; filename=nutrients.csv"},
    )
