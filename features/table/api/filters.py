"""Query-параметры таблиц как общие зависимости.

FastAPI ставит параметры зависимостей после собственных параметров эндпоинта,
поэтому сортировка и пагинация тоже вынесены сюда: порядок параметров в
OpenAPI остаётся прежним.
"""

from typing import Annotated, Literal
from uuid import UUID

from fastapi import Query

from ..domain.filters import ExactIds, Page, Sorting, TableFilters


def _contains(what: str):
    return Query(description=f"Фильтр по {what} (часть, без учёта регистра)")


Region = Annotated[str | None, _contains("региону")]
Category = Annotated[str | None, _contains("категории")]
Subcategory = Annotated[str | None, _contains("подкатегории")]
Product = Annotated[str | None, _contains("названию продукта")]
NutrientType = Annotated[str | None, _contains("типу нутриента")]
NutrientName = Annotated[str | None, _contains("названию нутриента")]
Order = Literal["asc", "desc"]


def product_filters(
    region: Region = None,
    category: Category = None,
    subcategory: Subcategory = None,
    product: Product = None,
) -> TableFilters:
    return TableFilters(
        region=region, category=category, subcategory=subcategory, product=product
    )


def pivot_filters(
    region: Region = None,
    category: Category = None,
    subcategory: Subcategory = None,
    product: Product = None,
    nutrient_type: NutrientType = None,
) -> TableFilters:
    return TableFilters(
        region=region,
        category=category,
        subcategory=subcategory,
        product=product,
        nutrient_type=nutrient_type,
    )


def nutrient_filters(
    region: Region = None,
    category: Category = None,
    subcategory: Subcategory = None,
    product: Product = None,
    nutrient_type: NutrientType = None,
    nutrient_name: NutrientName = None,
) -> TableFilters:
    return TableFilters(
        region=region,
        category=category,
        subcategory=subcategory,
        product=product,
        nutrient_type=nutrient_type,
        nutrient_name=nutrient_name,
    )


def csv_filters(
    region: Region = None,
    category: Category = None,
    product: Product = None,
    nutrient_type: NutrientType = None,
    nutrient_name: NutrientName = None,
) -> TableFilters:
    return TableFilters(
        region=region,
        category=category,
        product=product,
        nutrient_type=nutrient_type,
        nutrient_name=nutrient_name,
    )


def exact_ids(
    category_id: Annotated[
        UUID | None, Query(description="Точный фильтр по категории (ID)")
    ] = None,
    subcategory_id: Annotated[
        UUID | None, Query(description="Точный фильтр по подкатегории (ID)")
    ] = None,
    region_id: Annotated[
        UUID | None, Query(description="Точный фильтр по региону (ID)")
    ] = None,
) -> ExactIds:
    return ExactIds(
        category_id=category_id, subcategory_id=subcategory_id, region_id=region_id
    )


def table_sorting(
    sort_by: Annotated[
        str, Query(description="Колонка для сортировки")
    ] = "product_name",
    sort_order: Annotated[Order, Query(description="Направление сортировки")] = "asc",
) -> Sorting:
    return Sorting(sort_by, sort_order)


def map_sorting(
    sort_by: Annotated[
        str,
        Query(
            description="Колонка для сортировки (product_name, category_name, region_name)"
        ),
    ] = "product_name",
    sort_order: Annotated[Order, Query(description="Направление сортировки")] = "asc",
) -> Sorting:
    return Sorting(sort_by, sort_order)


def csv_sorting(
    sort_by: Annotated[
        str, Query(description="product_name / region_name / nutrient_name / quantity")
    ] = "product_name",
    sort_order: Annotated[Order, Query()] = "asc",
) -> Sorting:
    return Sorting(sort_by, sort_order)


def table_page(
    limit: Annotated[int, Query(ge=1, le=10000, description="Максимум строк")] = 1000,
    offset: Annotated[int, Query(ge=0, description="Сдвиг (пагинация)")] = 0,
) -> Page:
    return Page(limit, offset)


def csv_page(
    limit: Annotated[int, Query(ge=1, le=50000)] = 10000,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page:
    return Page(limit, offset)
