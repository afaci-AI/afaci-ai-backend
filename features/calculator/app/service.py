"""Сценарии калькулятора: расчёт рецептуры и оптимизация.

Загрузка данных идёт через порты; математика — в `domain`. Сумма ингредиентов,
наличие эталона и продуктов проверяются здесь и переводятся в общие ошибки.
"""

from __future__ import annotations

import asyncio
from uuid import UUID

from core.errors import BadRequestError, NotFoundError, UnprocessableError

from ..domain import (
    REQUIRED_SUM,
    SUM_TOLERANCE,
    CandidateItem,
    CostOptimizationConstraints,
    OptimizationInfeasibleError,
    RecipeOptimizationError,
    compute_report,
    optimize_cost,
    optimize_recipe,
)
from .ports import ProductNutrientReader, ReferenceReader


class RecipeCalculator:
    def __init__(
        self, references: ReferenceReader, products: ProductNutrientReader
    ) -> None:
        self._references = references
        self._products = products

    # ------------------------------------------------------------ общее
    async def _reference(self, reference_id: UUID) -> dict:
        reference = await self._references.get_reference(reference_id)
        if reference is None:
            raise NotFoundError("Эталонный белок не найден.")
        return reference

    async def _products_by_id(self, ids: list[UUID]) -> dict:
        return await self._products.load_products(ids)

    @staticmethod
    def _require_found(requested: list[str], products: dict) -> None:
        missing = [pid for pid in requested if pid not in products]
        if missing:
            raise NotFoundError(f"Продукты не найдены: {', '.join(missing)}")

    # ----------------------------------------------------------- расчёт
    async def compute(self, reference_protein_id: UUID, items: list[dict]) -> dict:
        """items: [{product_id: UUID|str, amount_g: float}, ...]

        Валидирует сумму (= 100 ± SUM_TOLERANCE), грузит эталон и продукты,
        возвращает полный отчёт `compute_report`.
        """
        if not items:
            raise BadRequestError("Список ингредиентов пуст.")

        total = sum(it["amount_g"] for it in items)
        if abs(total - REQUIRED_SUM) > SUM_TOLERANCE:
            raise BadRequestError(
                f"Сумма Xᵢ должна быть ровно {REQUIRED_SUM:.0f} г "
                f"(сейчас {total:.2f} г). Расчёт невозможен."
            )

        reference = await self._reference(reference_protein_id)
        products = await self._products_by_id([it["product_id"] for it in items])
        self._require_found([str(it["product_id"]) for it in items], products)

        enriched = [
            {**products[str(it["product_id"])], "amount_g": it["amount_g"]}
            for it in items
        ]
        return compute_report(enriched, reference)

    # ------------------------------------------------- оптимизация цены
    async def optimize_cost(
        self,
        reference_protein_id: UUID,
        candidates: list[dict],
        constraints: dict,
    ) -> dict:
        """candidates: [{product_id, price_per_kg, min_amount_g, max_amount_g}];
        constraints: {bc_min?, kras_max?}.
        Возвращает {optimal_items, total_cost_per_100g, report}."""
        if not candidates:
            raise BadRequestError("Список кандидатов пуст.")

        reference = await self._reference(reference_protein_id)
        products = await self._products_by_id(
            [UUID(c["product_id"]) for c in candidates]
        )
        self._require_found([c["product_id"] for c in candidates], products)

        domain_candidates = [
            _candidate(
                c["product_id"],
                products,
                float(c["price_per_kg"]),
                float(c.get("min_amount_g", 0.0)),
                float(c.get("max_amount_g", 100.0)),
            )
            for c in candidates
        ]
        try:
            opt = optimize_cost(
                domain_candidates,
                reference,
                CostOptimizationConstraints(
                    bc_min=constraints.get("bc_min"),
                    kras_max=constraints.get("kras_max"),
                ),
            )
        except OptimizationInfeasibleError as e:
            raise UnprocessableError(e.detail) from e

        amounts = opt["amounts"]
        enriched = [
            {**products[c.product_id], "amount_g": amounts[i]}
            for i, c in enumerate(domain_candidates)
        ]
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
            "report": compute_report(enriched, reference),
        }

    # --------------------------------------------- оптимизация состава
    async def optimize_composition(
        self, reference_protein_id: UUID, items: list[dict], mode: str
    ) -> dict:
        reference = await self._reference(reference_protein_id)
        products = await self._products_by_id([UUID(i["product_id"]) for i in items])
        self._require_found([i["product_id"] for i in items], products)
        candidates = [
            _candidate(
                item["product_id"],
                products,
                item.get("price_per_kg") or 0.0,
                item["min_amount_g"],
                item["max_amount_g"],
            )
            for item in items
        ]
        try:
            result = await asyncio.to_thread(
                optimize_recipe,
                candidates,
                reference,
                [item["amount_g"] for item in items],
                mode,
            )
        except RecipeOptimizationError as exc:
            raise UnprocessableError({"code": exc.code, "message": str(exc)}) from exc
        for output, source in zip(result["optimal_items"], items, strict=True):
            output["price_per_kg"] = source.get("price_per_kg")
        return result


def _candidate(
    product_id: str,
    products: dict,
    price: float,
    low: float,
    high: float,
) -> CandidateItem:
    product = products[product_id]
    return CandidateItem(
        product_id=product_id,
        name=product["name"],
        chem=product["chem"],
        amino=product["amino"],
        region=product.get("region"),
        subcategory=product.get("subcategory"),
        price_per_kg=price,
        min_amount_g=low,
        max_amount_g=high,
    )
