"""Продукты и нутриенты: CRUD, массовое создание, автосоздание, бизнес-аудит."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header

from core.db.models import User
from core.security import get_current_user_optional, require_editor

from ..app import Caller, NutrientService, ProductService
from .deps import get_nutrient_service, get_product_service
from .schemas import (
    NutrientBulkCreate,
    NutrientCreate,
    NutrientUpdate,
    ProductAutoCreate,
    ProductCount,
    ProductCreate,
    ProductUpdate,
)

router = APIRouter(prefix="/api/v1")

CurrentUserOpt = Annotated[User | None, Depends(get_current_user_optional)]
Products = Annotated[ProductService, Depends(get_product_service)]
Nutrients = Annotated[NutrientService, Depends(get_nutrient_service)]
EDITOR = [Depends(require_editor)]
Authorization = Annotated[str | None, Header()]


# ==================== PRODUCTS ====================
@router.post("/products", status_code=201, tags=["Products"], dependencies=EDITOR)
async def api_create_product(
    data: ProductCreate,
    service: Products,
    authorization: Authorization = None,
    current_user: CurrentUserOpt = None,
):
    return await service.create(data.model_dump(), Caller(current_user, authorization))


@router.get("/products", tags=["Products"])
async def api_list_products(service: Products):
    return await service.list()


@router.get(
    "/products/count",
    tags=["Products"],
    response_model=ProductCount,
    summary="Общее количество продуктов питания",
    description=(
        "Возвращает число всех продуктов в базе. Не принимает фильтров, поиска "
        'и пагинации; для пустой базы возвращает `{"count": 0}`.'
    ),
)
async def api_count_products(service: Products):
    return ProductCount(count=await service.count())


@router.get("/products/{id}", tags=["Products"])
async def api_get_product(id: UUID, service: Products):
    return await service.get(id)


@router.delete("/products/{id}", tags=["Products"], dependencies=EDITOR)
async def api_delete_product(
    id: UUID,
    service: Products,
    authorization: Authorization = None,
    current_user: CurrentUserOpt = None,
):
    return await service.delete(id, Caller(current_user, authorization))


@router.patch("/products/{id}", tags=["Products"], dependencies=EDITOR)
async def api_update_product(
    id: UUID,
    data: ProductUpdate,
    service: Products,
    authorization: Authorization = None,
    current_user: CurrentUserOpt = None,
):
    return await service.update(
        id, data.model_dump(exclude_unset=True), Caller(current_user, authorization)
    )


@router.post("/products/bulk", status_code=201, tags=["Products"], dependencies=EDITOR)
async def api_bulk_products(
    data: list[ProductCreate],
    service: Products,
    authorization: Authorization = None,
    current_user: CurrentUserOpt = None,
):
    return await service.bulk_create(
        [p.model_dump() for p in data], Caller(current_user, authorization)
    )


@router.get("/products/by-region/{id}", tags=["Products"])
async def api_products_by_region(id: UUID, service: Products):
    return await service.by_region(id)


@router.get("/products/by-category/{id}", tags=["Products"])
async def api_products_by_category(id: UUID, service: Products):
    return await service.by_category(id)


@router.post("/products/auto", status_code=201, tags=["Products"], dependencies=EDITOR)
async def api_auto_create_product(
    data: ProductAutoCreate,
    service: Products,
    authorization: Authorization = None,
    current_user: CurrentUserOpt = None,
):
    return await service.auto_create(
        data.model_dump(), Caller(current_user, authorization)
    )


@router.post(
    "/products/auto/bulk", status_code=201, tags=["Products"], dependencies=EDITOR
)
async def api_auto_bulk_products(
    data: list[ProductAutoCreate],
    service: Products,
    authorization: Authorization = None,
    current_user: CurrentUserOpt = None,
):
    return await service.auto_bulk(
        [item.model_dump() for item in data], Caller(current_user, authorization)
    )


# ==================== NUTRIENTS ====================
@router.post("/nutrients", status_code=201, tags=["Nutrients"], dependencies=EDITOR)
async def api_create_nutrient(
    data: NutrientCreate,
    service: Nutrients,
    authorization: Authorization = None,
    current_user: CurrentUserOpt = None,
):
    return await service.create(data.model_dump(), Caller(current_user, authorization))


@router.get("/nutrients", tags=["Nutrients"])
async def api_list_nutrients(service: Nutrients):
    return await service.list()


@router.get("/nutrients/{id}", tags=["Nutrients"])
async def api_get_nutrient(id: UUID, service: Nutrients):
    return await service.get(id)


@router.delete("/nutrients/{id}", tags=["Nutrients"], dependencies=EDITOR)
async def api_delete_nutrient(
    id: UUID,
    service: Nutrients,
    authorization: Authorization = None,
    current_user: CurrentUserOpt = None,
):
    return await service.delete(id, Caller(current_user, authorization))


@router.patch("/nutrients/{id}", tags=["Nutrients"], dependencies=EDITOR)
async def api_update_nutrient(
    id: UUID,
    data: NutrientUpdate,
    service: Nutrients,
    authorization: Authorization = None,
    current_user: CurrentUserOpt = None,
):
    return await service.update(
        id, data.model_dump(exclude_unset=True), Caller(current_user, authorization)
    )


@router.get("/nutrients/product/{id}", tags=["Nutrients"])
async def api_product_nutrients(id: UUID, service: Nutrients):
    return await service.by_product(id)


@router.post(
    "/nutrients/bulk", status_code=201, tags=["Nutrients"], dependencies=EDITOR
)
async def api_bulk_nutrients(
    data: NutrientBulkCreate,
    service: Nutrients,
    authorization: Authorization = None,
    current_user: CurrentUserOpt = None,
):
    return await service.bulk_create(
        [n.model_dump() for n in data.items], Caller(current_user, authorization)
    )
