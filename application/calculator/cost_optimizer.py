"""
Application-слой оптимизации стоимости рецептуры.

Загружает эталонный белок и пищевую информацию о продуктах из БД,
делегирует математику в domain/calculator/optimizer.py, затем
прогоняет compute_report для полного отчёта по оптимальной рецептуре.
"""
from uuid import UUID
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from domain.calculator import (
    optimize_cost,
    compute_report,
    CandidateItem,
    CostOptimizationConstraints,
    OptimizationInfeasibleError,
)
from application.calculator.calculator_service import load_reference, load_products


async def optimize_recipe_cost(
    db: AsyncSession,
    reference_protein_id: UUID,
    candidates: list[dict],
    constraints: dict,
) -> dict:
    """
    candidates: [{product_id: str, price_per_kg: float,
                  min_amount_g: float, max_amount_g: float}]
    constraints: {bc_min?: float, kras_max?: float}

    Возвращает {optimal_items, total_cost_per_100g, report}.
    """
    if not candidates:
        raise HTTPException(status_code=400, detail="Список кандидатов пуст.")

    reference = await load_reference(db, reference_protein_id)
    if reference is None:
        raise HTTPException(status_code=404, detail="Эталонный белок не найден.")

    ids = [UUID(c["product_id"]) for c in candidates]
    products = await load_products(db, ids)

    missing = [c["product_id"] for c in candidates if c["product_id"] not in products]
    if missing:
        raise HTTPException(
            status_code=404,
            detail=f"Продукты не найдены: {', '.join(missing)}",
        )

    domain_candidates = [
        CandidateItem(
            product_id=c["product_id"],
            name=products[c["product_id"]]["name"],
            chem=products[c["product_id"]]["chem"],
            amino=products[c["product_id"]]["amino"],
            region=products[c["product_id"]].get("region"),
            subcategory=products[c["product_id"]].get("subcategory"),
            price_per_kg=float(c["price_per_kg"]),
            min_amount_g=float(c.get("min_amount_g", 0.0)),
            max_amount_g=float(c.get("max_amount_g", 100.0)),
        )
        for c in candidates
    ]

    domain_constraints = CostOptimizationConstraints(
        bc_min=constraints.get("bc_min"),
        kras_max=constraints.get("kras_max"),
    )

    try:
        opt = optimize_cost(domain_candidates, reference, domain_constraints)
    except OptimizationInfeasibleError as e:
        raise HTTPException(status_code=422, detail=e.detail)

    amounts = opt["amounts"]

    enriched = [
        {**products[c.product_id], "amount_g": amounts[i]}
        for i, c in enumerate(domain_candidates)
    ]
    report = compute_report(enriched, reference)

    return {
        "optimal_items": [
            {
                "product_id": c.product_id,
                "amount_g": amounts[i],
                "price_per_kg": c.price_per_kg,
            }
            for i, c in enumerate(domain_candidates)
        ],
        "total_cost_per_100g": opt["total_cost_per_100g"],
        "report": report,
    }
