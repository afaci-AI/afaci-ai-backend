"""Load recipe data and run the numerical search outside the event loop."""

from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from application.calculator.calculator_service import load_products, load_reference
from domain.calculator.optimizer import CandidateItem
from domain.calculator.recipe_optimizer import RecipeOptimizationError, optimize_recipe


async def optimize_recipe_composition(
    db: AsyncSession, reference_protein_id: UUID, items: list[dict], mode: str
) -> dict:
    reference = await load_reference(db, reference_protein_id)
    if reference is None:
        raise HTTPException(status_code=404, detail="Эталонный белок не найден.")
    products = await load_products(db, [UUID(item["product_id"]) for item in items])
    missing = [
        item["product_id"] for item in items if item["product_id"] not in products
    ]
    if missing:
        raise HTTPException(
            status_code=404, detail=f"Продукты не найдены: {', '.join(missing)}"
        )
    candidates = [
        CandidateItem(
            product_id=item["product_id"],
            name=products[item["product_id"]]["name"],
            chem=products[item["product_id"]]["chem"],
            amino=products[item["product_id"]]["amino"],
            region=products[item["product_id"]].get("region"),
            subcategory=products[item["product_id"]].get("subcategory"),
            price_per_kg=item.get("price_per_kg") or 0.0,
            min_amount_g=item["min_amount_g"],
            max_amount_g=item["max_amount_g"],
        )
        for item in items
    ]
    try:
        result = await run_in_threadpool(
            optimize_recipe,
            candidates,
            reference,
            [item["amount_g"] for item in items],
            mode,
        )
        for output, source in zip(result["optimal_items"], items, strict=True):
            output["price_per_kg"] = source.get("price_per_kg")
        return result
    except RecipeOptimizationError as exc:
        raise HTTPException(
            status_code=422, detail={"code": exc.code, "message": str(exc)}
        ) from exc
