"""Справочники: категории, подкатегории, регионы, единицы, типы и названия нутриентов.

Простые справочники (категории, регионы, единицы, типы нутриентов) устроены
одинаково и регистрируются по описанию `DictionarySpec`; подкатегории и названия
нутриентов имеют родителя и единицу, поэтому создаются и меняются отдельно.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from core.security import require_editor

from ..app import CatalogService
from ..domain.dictionaries import (
    CATEGORIES,
    NUTRIENT_NAMES,
    NUTRIENT_TYPES,
    REGIONS,
    SUBCATEGORIES,
    UNITS,
    DictionarySpec,
)
from .deps import get_catalog_service
from .schemas import (
    NutrientNameCreate,
    NutrientNameUpdate,
    SimpleBulkCreate,
    SimpleCreate,
    SimpleUpdate,
    SubcategoryCreate,
    SubcategoryUpdate,
)

router = APIRouter(prefix="/api/v1")

Service = Annotated[CatalogService, Depends(get_catalog_service)]
EDITOR = [Depends(require_editor)]


def _named(fn, name: str):
    """FastAPI строит operationId и summary из имени функции."""
    fn.__name__ = name
    return fn


def _register_read_delete(spec: DictionarySpec, *, list_filter: bool = False) -> None:
    path, tag = spec.path, [spec.tag]

    if list_filter:

        async def list_items(service: Service, name: str | None = None):
            return await service.list(spec, name)

    else:

        async def list_items(service: Service):
            return await service.list(spec)

    async def get_one(id: UUID, service: Service):
        return await service.get_one(spec, id)

    async def delete(id: UUID, service: Service):
        return await service.delete(spec, id)

    router.get(path, tags=tag)(_named(list_items, f"api_list_{spec.plural}"))
    router.get(path + "/{id}", tags=tag)(_named(get_one, f"api_get_{spec.singular}"))
    router.delete(path + "/{id}", tags=tag, dependencies=EDITOR)(
        _named(delete, f"api_delete_{spec.singular}")
    )


def _register_bulk(spec: DictionarySpec) -> None:
    async def bulk(data: SimpleBulkCreate, service: Service):
        return await service.bulk(spec, data.names)

    router.post(
        spec.path + "/bulk", status_code=201, tags=[spec.tag], dependencies=EDITOR
    )(_named(bulk, f"api_bulk_{spec.plural}"))


def register_simple(spec: DictionarySpec) -> None:
    """Категории, регионы, единицы, типы нутриентов: создать, прочитать, изменить имя."""

    async def create(data: SimpleCreate, service: Service):
        return await service.create(spec, data.model_dump())

    async def update(id: UUID, data: SimpleUpdate, service: Service):
        return await service.rename(spec, id, data.name)

    router.post(spec.path, status_code=201, tags=[spec.tag], dependencies=EDITOR)(
        _named(create, f"api_create_{spec.singular}")
    )
    _register_read_delete(spec, list_filter=spec.searchable)
    router.patch(spec.path + "/{id}", tags=[spec.tag], dependencies=EDITOR)(
        _named(update, f"api_update_{spec.singular}")
    )
    _register_bulk(spec)


# ==================== CATEGORIES ====================
register_simple(CATEGORIES)


# ==================== SUBCATEGORIES ====================
@router.post(
    "/subcategories", status_code=201, tags=["Subcategories"], dependencies=EDITOR
)
async def api_create_subcategory(data: SubcategoryCreate, service: Service):
    return await service.create_subcategory(data.model_dump())


_register_read_delete(SUBCATEGORIES)


@router.patch("/subcategories/{id}", tags=["Subcategories"], dependencies=EDITOR)
async def api_update_subcategory(id: UUID, data: SubcategoryUpdate, service: Service):
    return await service.update_subcategory(
        id,
        name=data.name,
        category_id=data.category_id,
        provided=set(data.model_fields_set),
    )


# ==================== REGIONS, UNITS, NUTRIENT TYPES ====================
register_simple(REGIONS)
register_simple(UNITS)
register_simple(NUTRIENT_TYPES)


# ==================== NUTRIENT NAMES ====================
@router.post(
    "/nutrient-names", status_code=201, tags=["Nutrient Names"], dependencies=EDITOR
)
async def api_create_nutrient_name(data: NutrientNameCreate, service: Service):
    return await service.create_nutrient_name(data.model_dump())


_register_read_delete(NUTRIENT_NAMES)


@router.patch("/nutrient-names/{id}", tags=["Nutrient Names"], dependencies=EDITOR)
async def api_update_nutrient_name(
    id: UUID, data: NutrientNameUpdate, service: Service
):
    return await service.update_nutrient_name(
        id,
        name=data.name,
        nutrient_type_id=data.nutrient_type_id,
        unit_id=data.unit_id,
        provided=set(data.model_fields_set),
    )


_register_bulk(NUTRIENT_NAMES)
