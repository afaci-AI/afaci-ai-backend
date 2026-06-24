"""
Эндпоинты Калькулятора пищевой и биологической ценности.

  GET  /api/v1/calculator/reference-proteins  — эталоны ФАО/ВОЗ (для селектора и Табл. 4)
  GET  /api/v1/calculator/recipes             — сохранённые рецептуры (загружаемые примеры)
  POST /api/v1/calculator/compute             — расчёт по списку ингредиентов + эталону
"""
from uuid import UUID
from typing import List

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from auth import get_current_user
from models import User
from calc_service import compute_recipe

TAG = "Calculator"
router = APIRouter(prefix="/api/v1/calculator", tags=[TAG])


# ----------------------------- схемы -----------------------------
class CalcItem(BaseModel):
    product_id: UUID
    amount_g: float


class CalcRequest(BaseModel):
    reference_protein_id: UUID
    items: List[CalcItem]


@router.get("/reference-proteins", summary="Эталонные белки ФАО/ВОЗ")
async def list_reference_proteins(db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(text(
        "SELECT id, name, year, is_default, description FROM reference_proteins "
        "ORDER BY year"
    ))).mappings().all()
    result = []
    for rp in rows:
        vals = (await db.execute(
            text("SELECT amino_acid, value, sort_order FROM reference_protein_values "
                 "WHERE reference_protein_id = :id ORDER BY sort_order"),
            {"id": rp["id"]},
        )).mappings().all()
        result.append({
            "id": str(rp["id"]),
            "name": rp["name"],
            "year": rp["year"],
            "is_default": rp["is_default"],
            "description": rp["description"],
            "values": [{"amino_acid": v["amino_acid"], "value": v["value"]} for v in vals],
        })
    return result


@router.get("/recipes", summary="Сохранённые рецептуры (примеры)")
async def list_recipes(db: AsyncSession = Depends(get_db)):
    recipes = (await db.execute(text(
        "SELECT id, name, description, sample_type FROM recipes ORDER BY name"
    ))).mappings().all()
    result = []
    for rc in recipes:
        items = (await db.execute(
            text("""
                SELECT ri.product_id, ri.amount_g, ri.sort_order,
                       p.name AS product_name, r.name AS region, s.name AS subcategory
                FROM recipe_items ri
                JOIN products p ON p.id = ri.product_id
                JOIN regions r ON r.id = p.region_id
                LEFT JOIN subcategories s ON s.id = p.subcategory_id
                WHERE ri.recipe_id = :id
                ORDER BY ri.sort_order
            """),
            {"id": rc["id"]},
        )).mappings().all()
        result.append({
            "id": str(rc["id"]),
            "name": rc["name"],
            "description": rc["description"],
            "sample_type": rc["sample_type"],
            "items": [{
                "product_id": str(it["product_id"]),
                "name": it["product_name"],
                "region": it["region"],
                "subcategory": it["subcategory"],
                "amount_g": it["amount_g"],
            } for it in items],
        })
    return result


# --------------------------- расчёт ------------------------------
@router.post("/compute", summary="Рассчитать пищевую и биологическую ценность")
async def compute(
    req: CalcRequest,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    items = [{"product_id": it.product_id, "amount_g": it.amount_g} for it in req.items]
    return await compute_recipe(db, req.reference_protein_id, items)
