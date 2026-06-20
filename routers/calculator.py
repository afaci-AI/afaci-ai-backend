"""
Эндпоинты Калькулятора пищевой и биологической ценности.

  GET  /api/v1/calculator/reference-proteins  — эталоны ФАО/ВОЗ (для селектора и Табл. 4)
  GET  /api/v1/calculator/recipes             — сохранённые рецептуры (загружаемые примеры)
  POST /api/v1/calculator/compute             — расчёт по списку ингредиентов + эталону
"""
from uuid import UUID
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text, bindparam
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from calculator import compute_report, NAK_GROUPS, SUM_TOLERANCE

TAG = "Calculator"
router = APIRouter(prefix="/api/v1/calculator", tags=[TAG])

CHEM_TYPE = "Химический состав"
AMINO_TYPE = "Аминокислотный состав"
REQUIRED_SUM = 100.0


# ----------------------------- схемы -----------------------------
class CalcItem(BaseModel):
    product_id: UUID
    amount_g: float


class CalcRequest(BaseModel):
    reference_protein_id: UUID
    items: List[CalcItem]


# ----------------------- справочные данные -----------------------
async def _load_reference(db: AsyncSession, ref_id: UUID) -> Optional[dict]:
    rp = (await db.execute(
        text("SELECT id, name, year, description FROM reference_proteins WHERE id = :id"),
        {"id": ref_id},
    )).mappings().first()
    if not rp:
        return None
    vals = (await db.execute(
        text("SELECT amino_acid, value FROM reference_protein_values "
             "WHERE reference_protein_id = :id"),
        {"id": ref_id},
    )).mappings().all()
    return {
        "id": str(rp["id"]),
        "name": rp["name"],
        "year": rp["year"],
        "description": rp["description"],
        "values": {v["amino_acid"]: v["value"] for v in vals},
    }


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
async def _load_products(db: AsyncSession, ids: List[UUID]) -> dict:
    q = text("""
        SELECT p.id AS product_id, p.name, r.name AS region, s.name AS subcategory,
               nn.name AS nutrient, nt.name AS ntype, n.quantity
        FROM products p
        JOIN regions r ON r.id = p.region_id
        LEFT JOIN subcategories s ON s.id = p.subcategory_id
        LEFT JOIN nutrients n ON n.id_product = p.id
        LEFT JOIN nutrients_names nn ON nn.id = n.id_name_component
        LEFT JOIN nutrients_types nt ON nt.id = nn.nutrient_type_id
        WHERE p.id IN :ids
    """).bindparams(bindparam("ids", expanding=True))
    rows = (await db.execute(q, {"ids": ids})).mappings().all()

    products: dict = {}
    for row in rows:
        pid = str(row["product_id"])
        prod = products.setdefault(pid, {
            "product_id": pid,
            "name": row["name"],
            "region": row["region"],
            "subcategory": row["subcategory"],
            "chem": {},
            "amino": {},
        })
        if row["nutrient"] is None:
            continue
        if row["ntype"] == CHEM_TYPE:
            prod["chem"][row["nutrient"]] = row["quantity"]
        elif row["ntype"] == AMINO_TYPE:
            prod["amino"][row["nutrient"]] = row["quantity"]
    return products


@router.post("/compute", summary="Рассчитать пищевую и биологическую ценность")
async def compute(req: CalcRequest, db: AsyncSession = Depends(get_db)):
    if not req.items:
        raise HTTPException(status_code=400, detail="Список ингредиентов пуст.")

    total = sum(it.amount_g for it in req.items)
    if abs(total - REQUIRED_SUM) > SUM_TOLERANCE:
        raise HTTPException(
            status_code=400,
            detail=f"Сумма Xᵢ должна быть ровно {REQUIRED_SUM:.0f} г "
                   f"(сейчас {total:.2f} г). Расчёт невозможен.",
        )

    reference = await _load_reference(db, req.reference_protein_id)
    if reference is None:
        raise HTTPException(status_code=404, detail="Эталонный белок не найден.")

    ids = [it.product_id for it in req.items]
    products = await _load_products(db, ids)

    missing = [str(it.product_id) for it in req.items if str(it.product_id) not in products]
    if missing:
        raise HTTPException(status_code=404, detail=f"Продукты не найдены: {', '.join(missing)}")

    items = []
    for it in req.items:
        p = products[str(it.product_id)]
        items.append({**p, "amount_g": it.amount_g})

    return compute_report(items, reference)
