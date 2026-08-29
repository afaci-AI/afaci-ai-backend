"""
Сервис расчёта рецептуры: загрузка эталона и продуктов из БД + вызов
чистой логики `compute_report`. Переиспользуется калькулятором, сохранением
рецептур и ранжированием, чтобы не дублировать SQL и валидацию.
"""

from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession

from domain.calculator import REQUIRED_SUM, SUM_TOLERANCE, compute_report

CHEM_TYPE = "Химический состав"
AMINO_TYPE = "Аминокислотный состав"


async def load_reference(db: AsyncSession, ref_id: UUID) -> dict | None:
    rp = (
        (
            await db.execute(
                text(
                    "SELECT id, name, year, description FROM reference_proteins WHERE id = :id"
                ),
                {"id": ref_id},
            )
        )
        .mappings()
        .first()
    )
    if not rp:
        return None
    vals = (
        (
            await db.execute(
                text(
                    "SELECT amino_acid, value FROM reference_protein_values "
                    "WHERE reference_protein_id = :id"
                ),
                {"id": ref_id},
            )
        )
        .mappings()
        .all()
    )
    return {
        "id": str(rp["id"]),
        "name": rp["name"],
        "year": rp["year"],
        "description": rp["description"],
        "values": {v["amino_acid"]: v["value"] for v in vals},
    }


async def load_products(db: AsyncSession, ids: list[UUID]) -> dict:
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
        prod = products.setdefault(
            pid,
            {
                "product_id": pid,
                "name": row["name"],
                "region": row["region"],
                "subcategory": row["subcategory"],
                "chem": {},
                "amino": {},
            },
        )
        if row["nutrient"] is None:
            continue
        if row["ntype"] == CHEM_TYPE:
            prod["chem"][row["nutrient"]] = row["quantity"]
        elif row["ntype"] == AMINO_TYPE:
            prod["amino"][row["nutrient"]] = row["quantity"]
    return products


async def compute_recipe(
    db: AsyncSession,
    reference_protein_id: UUID,
    items: list[dict],
) -> dict:
    """
    items: [{product_id: UUID|str, amount_g: float}, ...]

    Валидирует сумму (= 100 ± SUM_TOLERANCE), грузит эталон и продукты,
    возвращает полный отчёт `compute_report`. Бросает HTTPException при ошибках.
    """
    if not items:
        raise HTTPException(status_code=400, detail="Список ингредиентов пуст.")

    total = sum(it["amount_g"] for it in items)
    if abs(total - REQUIRED_SUM) > SUM_TOLERANCE:
        raise HTTPException(
            status_code=400,
            detail=f"Сумма Xᵢ должна быть ровно {REQUIRED_SUM:.0f} г "
            f"(сейчас {total:.2f} г). Расчёт невозможен.",
        )

    reference = await load_reference(db, reference_protein_id)
    if reference is None:
        raise HTTPException(status_code=404, detail="Эталонный белок не найден.")

    ids = [it["product_id"] for it in items]
    products = await load_products(db, ids)

    missing = [
        str(it["product_id"]) for it in items if str(it["product_id"]) not in products
    ]
    if missing:
        raise HTTPException(
            status_code=404, detail=f"Продукты не найдены: {', '.join(missing)}"
        )

    enriched = []
    for it in items:
        p = products[str(it["product_id"])]
        enriched.append({**p, "amount_g": it["amount_g"]})

    return compute_report(enriched, reference)
