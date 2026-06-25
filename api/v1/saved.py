"""
Сохранённые рецептуры, группы (как плейлисты) и ранжирование рецептур.
Все эндпоинты — только для авторизованного пользователя и только над своими данными.

  Группы:
    GET    /api/v1/saved/groups
    POST   /api/v1/saved/groups
    PATCH  /api/v1/saved/groups/{id}
    DELETE /api/v1/saved/groups/{id}

  Рецептуры:
    GET    /api/v1/saved/recipes
    GET    /api/v1/saved/recipes/{id}
    POST   /api/v1/saved/recipes
    PATCH  /api/v1/saved/recipes/{id}
    DELETE /api/v1/saved/recipes/{id}

  Ранжирование:
    POST   /api/v1/saved/ranking
"""
from uuid import UUID
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from infrastructure.db.session import get_db
from infrastructure.auth import get_current_user
from infrastructure.db.models import User, RecipeGroup, SavedRecipe, SavedRecipeItem
from application.calculator.calculator_service import compute_recipe

router = APIRouter(prefix="/api/v1/saved", tags=["Saved"])


# ============================ схемы ==============================
class GroupIn(BaseModel):
    name: str = Field(min_length=1)


class SavedItemIn(BaseModel):
    product_id: UUID
    amount_g: float


class SavedRecipeCreate(BaseModel):
    name: str = Field(min_length=1)
    group_id: Optional[UUID] = None
    new_group_name: Optional[str] = None
    reference_protein_id: UUID
    items: List[SavedItemIn]
    draft: bool = False


class SavedRecipeUpdate(BaseModel):
    name: Optional[str] = None
    group_id: Optional[UUID] = None
    reference_protein_id: Optional[UUID] = None
    items: Optional[List[SavedItemIn]] = None
    draft: Optional[bool] = None


class Weights(BaseModel):
    bc: float = 0.25
    kras: float = 0.25
    v: float = 0.25
    g: float = 0.25


class RankingRequest(BaseModel):
    recipe_ids: List[UUID]
    weights: Optional[Weights] = None


# ============================ помощники ============================
def _group_public(g: RecipeGroup, count: int = 0) -> dict:
    return {
        "id": str(g.id),
        "name": g.name,
        "created_at": g.created_at.isoformat() if g.created_at else None,
        "recipe_count": count,
    }


def _recipe_public(r: SavedRecipe, with_items: bool = False) -> dict:
    data = {
        "id": str(r.id),
        "name": r.name,
        "group_id": str(r.group_id) if r.group_id else None,
        "reference_protein_id": str(r.reference_protein_id),
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
        "metrics": {
            "bc": r.bc,
            "kras": r.kras,
            "V": r.v_coef,
            "G": r.g_coef,
            "energy_kcal": r.energy_kcal,
            "c_min_name": r.c_min_name,
            "c_min_score": r.c_min_score,
        },
    }
    if with_items:
        items = sorted(r.items, key=lambda it: it.sort_order)
        data["items"] = [{
            "product_id": str(it.product_id),
            "amount_g": it.amount_g,
            "sort_order": it.sort_order,
        } for it in items]
    return data


def _apply_metrics(r: SavedRecipe, report: dict) -> None:
    q = report.get("quality") or {}
    c_min = report.get("c_min") or {}
    r.bc = q.get("bc")
    r.kras = q.get("kras")
    r.v_coef = q.get("V")
    r.g_coef = q.get("G")
    r.energy_kcal = report.get("energy_kcal")
    r.c_min_name = c_min.get("name")
    r.c_min_score = c_min.get("score")


def _clear_metrics(r: SavedRecipe) -> None:
    """Сбросить показатели (рецептура-черновик без расчёта)."""
    r.bc = r.kras = r.v_coef = r.g_coef = r.energy_kcal = r.c_min_score = None
    r.c_min_name = None


async def _get_owned_recipe(db: AsyncSession, user: User, recipe_id: UUID,
                            with_items: bool = False) -> SavedRecipe:
    stmt = select(SavedRecipe).where(
        SavedRecipe.id == recipe_id, SavedRecipe.user_id == user.id
    )
    if with_items:
        stmt = stmt.options(selectinload(SavedRecipe.items))
    r = (await db.execute(stmt)).scalar_one_or_none()
    if r is None:
        raise HTTPException(status_code=404, detail="Рецептура не найдена.")
    return r


async def _validate_group(db: AsyncSession, user: User, group_id: UUID) -> None:
    g = (await db.execute(select(RecipeGroup).where(
        RecipeGroup.id == group_id, RecipeGroup.user_id == user.id
    ))).scalar_one_or_none()
    if g is None:
        raise HTTPException(status_code=404, detail="Группа не найдена.")


# ============================= группы =============================
@router.get("/groups", summary="Группы пользователя")
async def list_groups(db: AsyncSession = Depends(get_db),
                      user: User = Depends(get_current_user)):
    groups = (await db.execute(
        select(RecipeGroup).where(RecipeGroup.user_id == user.id)
        .order_by(RecipeGroup.created_at)
    )).scalars().all()
    counts = dict((await db.execute(
        select(SavedRecipe.group_id, func.count())
        .where(SavedRecipe.user_id == user.id, SavedRecipe.group_id.isnot(None))
        .group_by(SavedRecipe.group_id)
    )).all())
    return [_group_public(g, counts.get(g.id, 0)) for g in groups]


@router.post("/groups", summary="Создать группу")
async def create_group(req: GroupIn, db: AsyncSession = Depends(get_db),
                       user: User = Depends(get_current_user)):
    g = RecipeGroup(user_id=user.id, name=req.name.strip())
    db.add(g)
    await db.commit()
    await db.refresh(g)
    return _group_public(g, 0)


@router.patch("/groups/{group_id}", summary="Переименовать группу")
async def update_group(group_id: UUID, req: GroupIn,
                       db: AsyncSession = Depends(get_db),
                       user: User = Depends(get_current_user)):
    g = (await db.execute(select(RecipeGroup).where(
        RecipeGroup.id == group_id, RecipeGroup.user_id == user.id
    ))).scalar_one_or_none()
    if g is None:
        raise HTTPException(status_code=404, detail="Группа не найдена.")
    g.name = req.name.strip()
    await db.commit()
    await db.refresh(g)
    return _group_public(g)


@router.delete("/groups/{group_id}", summary="Удалить группу (рецептуры остаются без группы)")
async def delete_group(group_id: UUID, db: AsyncSession = Depends(get_db),
                       user: User = Depends(get_current_user)):
    g = (await db.execute(select(RecipeGroup).where(
        RecipeGroup.id == group_id, RecipeGroup.user_id == user.id
    ))).scalar_one_or_none()
    if g is None:
        raise HTTPException(status_code=404, detail="Группа не найдена.")
    await db.execute(
        SavedRecipe.__table__.update()
        .where(SavedRecipe.group_id == group_id)
        .values(group_id=None)
    )
    await db.delete(g)
    await db.commit()
    return {"ok": True}


# =========================== рецептуры ===========================
@router.get("/recipes", summary="Сохранённые рецептуры пользователя")
async def list_recipes(
    group_id: Optional[UUID] = Query(default=None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    stmt = select(SavedRecipe).where(SavedRecipe.user_id == user.id)
    if group_id is not None:
        stmt = stmt.where(SavedRecipe.group_id == group_id)
    stmt = stmt.order_by(SavedRecipe.updated_at.desc())
    recipes = (await db.execute(stmt)).scalars().all()
    return [_recipe_public(r) for r in recipes]


@router.get("/recipes/{recipe_id}", summary="Сохранённая рецептура с составом")
async def get_recipe(recipe_id: UUID, db: AsyncSession = Depends(get_db),
                     user: User = Depends(get_current_user)):
    r = await _get_owned_recipe(db, user, recipe_id, with_items=True)
    return _recipe_public(r, with_items=True)


@router.post("/recipes", summary="Сохранить рецептуру")
async def create_recipe(req: SavedRecipeCreate, db: AsyncSession = Depends(get_db),
                        user: User = Depends(get_current_user)):
    report = None
    if not req.draft:
        items = [{"product_id": it.product_id, "amount_g": it.amount_g} for it in req.items]
        report = await compute_recipe(db, req.reference_protein_id, items)

    group_id = req.group_id
    if req.new_group_name and req.new_group_name.strip():
        g = RecipeGroup(user_id=user.id, name=req.new_group_name.strip())
        db.add(g)
        await db.flush()
        group_id = g.id
    elif group_id is not None:
        await _validate_group(db, user, group_id)

    r = SavedRecipe(
        user_id=user.id,
        group_id=group_id,
        name=req.name.strip(),
        reference_protein_id=req.reference_protein_id,
    )
    if report:
        _apply_metrics(r, report)
    for idx, it in enumerate(req.items):
        r.items.append(SavedRecipeItem(
            product_id=it.product_id, amount_g=it.amount_g, sort_order=idx,
        ))
    db.add(r)
    await db.commit()
    await db.refresh(r)
    return _recipe_public(r)


@router.patch("/recipes/{recipe_id}", summary="Изменить рецептуру (имя/группа/состав)")
async def update_recipe(recipe_id: UUID, req: SavedRecipeUpdate,
                        db: AsyncSession = Depends(get_db),
                        user: User = Depends(get_current_user)):
    r = await _get_owned_recipe(db, user, recipe_id, with_items=True)
    fields = req.model_fields_set

    if "name" in fields and req.name is not None:
        r.name = req.name.strip()

    if "group_id" in fields:
        if req.group_id is not None:
            await _validate_group(db, user, req.group_id)
        r.group_id = req.group_id

    make_draft = req.draft is True
    new_ref = req.reference_protein_id if "reference_protein_id" in fields and req.reference_protein_id else r.reference_protein_id
    if "items" in fields and req.items is not None:
        r.reference_protein_id = new_ref
        if make_draft:
            _clear_metrics(r)
        else:
            items = [{"product_id": it.product_id, "amount_g": it.amount_g} for it in req.items]
            _apply_metrics(r, await compute_recipe(db, new_ref, items))
        r.items.clear()
        for idx, it in enumerate(req.items):
            r.items.append(SavedRecipeItem(
                product_id=it.product_id, amount_g=it.amount_g, sort_order=idx,
            ))
    elif "reference_protein_id" in fields and req.reference_protein_id:
        r.reference_protein_id = new_ref
        if make_draft:
            _clear_metrics(r)
        else:
            items = [{"product_id": it.product_id, "amount_g": it.amount_g}
                     for it in sorted(r.items, key=lambda x: x.sort_order)]
            _apply_metrics(r, await compute_recipe(db, new_ref, items))

    await db.commit()
    await db.refresh(r)
    return _recipe_public(r)


@router.delete("/recipes/{recipe_id}", summary="Удалить рецептуру")
async def delete_recipe(recipe_id: UUID, db: AsyncSession = Depends(get_db),
                        user: User = Depends(get_current_user)):
    r = await _get_owned_recipe(db, user, recipe_id)
    await db.delete(r)
    await db.commit()
    return {"ok": True}


# ========================= ранжирование =========================
def _normalize(values: List[Optional[float]], higher_is_better: bool) -> List[float]:
    """Нормировка показателя по выборке в [0..1]. None и нулевой разброс → нейтрально."""
    present = [v for v in values if v is not None]
    if not present:
        return [0.0 for _ in values]
    lo, hi = min(present), max(present)
    span = hi - lo
    out: List[float] = []
    for v in values:
        if v is None:
            out.append(0.0)
        elif span == 0:
            out.append(1.0)
        else:
            n = (v - lo) / span
            out.append(n if higher_is_better else 1.0 - n)
    return out


@router.post("/ranking", summary="Ранжирование рецептур по БЦ, КРАС, V, G")
async def ranking(req: RankingRequest, db: AsyncSession = Depends(get_db),
                  user: User = Depends(get_current_user)):
    if len(req.recipe_ids) < 1:
        raise HTTPException(status_code=400, detail="Выберите хотя бы одну рецептуру.")

    recipes = (await db.execute(
        select(SavedRecipe).where(
            SavedRecipe.user_id == user.id,
            SavedRecipe.id.in_(req.recipe_ids),
        )
    )).scalars().all()
    if len(recipes) != len(set(req.recipe_ids)):
        raise HTTPException(status_code=404, detail="Некоторые рецептуры не найдены.")

    group_names = dict((g.id, g.name) for g in (await db.execute(
        select(RecipeGroup).where(RecipeGroup.user_id == user.id)
    )).scalars().all())

    w = req.weights or Weights()
    wsum = (w.bc + w.kras + w.v + w.g) or 1.0
    wn = {"bc": w.bc / wsum, "kras": w.kras / wsum, "v": w.v / wsum, "g": w.g / wsum}

    n_bc = _normalize([r.bc for r in recipes], higher_is_better=True)
    n_kras = _normalize([r.kras for r in recipes], higher_is_better=False)
    n_v = _normalize([r.v_coef for r in recipes], higher_is_better=True)
    n_g = _normalize([r.g_coef for r in recipes], higher_is_better=False)

    results = []
    for i, r in enumerate(recipes):
        composite = (wn["bc"] * n_bc[i] + wn["kras"] * n_kras[i]
                     + wn["v"] * n_v[i] + wn["g"] * n_g[i])
        results.append({
            "recipe_id": str(r.id),
            "name": r.name,
            "group": group_names.get(r.group_id) if r.group_id else None,
            "bc": r.bc,
            "kras": r.kras,
            "V": r.v_coef,
            "G": r.g_coef,
            "normalized": {
                "bc": round(n_bc[i], 4),
                "kras": round(n_kras[i], 4),
                "V": round(n_v[i], 4),
                "G": round(n_g[i], 4),
            },
            "composite": round(composite, 4),
        })

    results.sort(key=lambda x: x["composite"], reverse=True)
    for rank, item in enumerate(results, start=1):
        item["rank"] = rank

    return {
        "weights": wn,
        "winner": results[0]["recipe_id"] if results else None,
        "ranking": results,
    }
