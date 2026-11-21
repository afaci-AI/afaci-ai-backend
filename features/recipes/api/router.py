"""
Сохранённые рецептуры и группы пользователя.

Группы:
    GET    /api/v1/saved/groups
    POST   /api/v1/saved/groups
    PATCH  /api/v1/saved/groups/{group_id}
    DELETE /api/v1/saved/groups/{group_id}

Рецептуры (со своим расчётом метрик на момент сохранения):
    GET    /api/v1/saved/recipes[?group_id=]
    GET    /api/v1/saved/recipes/{recipe_id}
    POST   /api/v1/saved/recipes
    PATCH  /api/v1/saved/recipes/{recipe_id}
    DELETE /api/v1/saved/recipes/{recipe_id}

Ранжирование:
    POST   /api/v1/saved/ranking
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from core.db.models import User
from core.security import get_current_user

from ..app import ItemData, RecipeChanges, RecipeService
from ..domain import RankingWeights
from .deps import get_recipe_service
from .presenters import group_public, recipe_public
from .schemas import (
    GroupIn,
    RankingRequest,
    SavedItemIn,
    SavedRecipeCreate,
    SavedRecipeUpdate,
    Weights,
)

router = APIRouter(prefix="/api/v1/saved", tags=["Saved"])

Service = Annotated[RecipeService, Depends(get_recipe_service)]
CurrentUser = Annotated[User, Depends(get_current_user)]


def _items(items: list[SavedItemIn]) -> list[ItemData]:
    return [ItemData(it.product_id, it.amount_g, it.price_per_kg) for it in items]


# ============================= группы =============================
@router.get("/groups", summary="Группы пользователя")
async def list_groups(service: Service, user: CurrentUser):
    return [group_public(g, count) for g, count in await service.list_groups(user.id)]


@router.post("/groups", summary="Создать группу")
async def create_group(req: GroupIn, service: Service, user: CurrentUser):
    return group_public(await service.create_group(user.id, req.name), 0)


@router.patch("/groups/{group_id}", summary="Переименовать группу")
async def update_group(
    group_id: UUID, req: GroupIn, service: Service, user: CurrentUser
):
    return group_public(await service.rename_group(user.id, group_id, req.name))


@router.delete(
    "/groups/{group_id}", summary="Удалить группу (рецептуры остаются без группы)"
)
async def delete_group(group_id: UUID, service: Service, user: CurrentUser):
    await service.delete_group(user.id, group_id)
    return {"ok": True}


# =========================== рецептуры ===========================
@router.get("/recipes", summary="Сохранённые рецептуры пользователя")
async def list_recipes(
    service: Service,
    user: CurrentUser,
    group_id: Annotated[UUID | None, Query()] = None,
):
    return [recipe_public(r) for r in await service.list_recipes(user.id, group_id)]


@router.get("/recipes/{recipe_id}", summary="Сохранённая рецептура с составом")
async def get_recipe(recipe_id: UUID, service: Service, user: CurrentUser):
    return recipe_public(await service.get_recipe(user.id, recipe_id), with_items=True)


@router.post("/recipes", summary="Сохранить рецептуру")
async def create_recipe(req: SavedRecipeCreate, service: Service, user: CurrentUser):
    recipe = await service.create_recipe(
        user.id,
        name=req.name,
        reference_protein_id=req.reference_protein_id,
        items=_items(req.items),
        draft=req.draft,
        group_id=req.group_id,
        new_group_name=req.new_group_name,
    )
    return recipe_public(recipe)


@router.patch("/recipes/{recipe_id}", summary="Изменить рецептуру (имя/группа/состав)")
async def update_recipe(
    recipe_id: UUID, req: SavedRecipeUpdate, service: Service, user: CurrentUser
):
    changes = RecipeChanges(
        name=req.name,
        group_id=req.group_id,
        reference_protein_id=req.reference_protein_id,
        items=None if req.items is None else _items(req.items),
        draft=req.draft,
        provided=set(req.model_fields_set),
    )
    return recipe_public(await service.update_recipe(user.id, recipe_id, changes))


@router.delete("/recipes/{recipe_id}", summary="Удалить рецептуру")
async def delete_recipe(recipe_id: UUID, service: Service, user: CurrentUser):
    await service.delete_recipe(user.id, recipe_id)
    return {"ok": True}


# ========================= ранжирование =========================
@router.post("/ranking", summary="Ранжирование рецептур по БЦ, КРАС, V, G")
async def ranking(req: RankingRequest, service: Service, user: CurrentUser):
    w = req.weights or Weights()
    weights = RankingWeights(bc=w.bc, kras=w.kras, utility=w.utility, g=w.g)
    return await service.rank(user.id, req.recipe_ids, weights)
