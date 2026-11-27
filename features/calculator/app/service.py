"""Сценарии калькулятора: расчёт рецептуры и оптимизация.

Загрузка данных идёт через порты; математика и правило суммы — в `domain`.
Здесь доменные ошибки и отсутствие эталона или продуктов переводятся в общие.
"""

from __future__ import annotations

import asyncio
from uuid import UUID

from core.errors import BadRequestError, NotFoundError, UnprocessableError

from ..domain import (
    PER_KILOGRAM,
    CandidateItem,
    CostOptimizationConstraints,
    EmptyRecipeError,
    InvalidRecipeSumError,
    OptimizationInfeasibleError,
    ProductNutrients,
    RecipeOptimizationError,
    compute_report,
    optimize_cost,
    optimize_recipe,
    validate_recipe_sum,
)
from .ports import (
    CompositionItemInput,
    CostCandidateInput,
    ProductNutrientReader,
    RecipeItemInput,
    ReferenceReader,
)


class RecipeCalculator:
    def __init__(
        self, references: ReferenceReader, products: ProductNutrientReader
    ) -> None:
        self._references = references
        self._products = products

    # ------------------------------------------------------------ общее
    async def _reference(self, reference_id: UUID) -> dict:
        """Эталон в формате формул."""
        reference = await self._references.get_reference(reference_id)
        if reference is None:
            raise NotFoundError("Эталонный белок не найден.")
        return reference.formula_input()

    async def _products_for(self, ids: list[UUID]) -> list[ProductNutrients]:
        """Продукты в порядке `ids`; NotFoundError, если какого-то нет.

        Хранилище отдаёт продукты по строковому id — это единственное место,
        где UUID переводится в строку.
        """
        found = await self._products.load_products(ids)
        missing = [str(pid) for pid in ids if str(pid) not in found]
        if missing:
            raise NotFoundError(f"Продукты не найдены: {', '.join(missing)}")
        return [found[str(pid)] for pid in ids]

    # ----------------------------------------------------------- расчёт
    async def compute(
        self, reference_protein_id: UUID, items: list[RecipeItemInput]
    ) -> dict:
        """Полный отчёт `compute_report`; сумма масс — ровно 100 г."""
        try:
            validate_recipe_sum(it.amount_g for it in items)
        except (EmptyRecipeError, InvalidRecipeSumError) as exc:
            raise BadRequestError(str(exc)) from exc

        reference = await self._reference(reference_protein_id)
        products = await self._products_for([it.product_id for it in items])
        enriched = [
            product.report_item(it.amount_g)
            for product, it in zip(products, items, strict=True)
        ]
        return compute_report(enriched, reference)

    # ------------------------------------------------- оптимизация цены
    async def optimize_cost(
        self,
        reference_protein_id: UUID,
        candidates: list[CostCandidateInput],
        constraints: CostOptimizationConstraints,
    ) -> dict:
        """Возвращает {optimal_items, total_cost_per_kg, report}."""
        if not candidates:
            raise BadRequestError("Список кандидатов пуст.")

        reference = await self._reference(reference_protein_id)
        products = await self._products_for([c.product_id for c in candidates])
        domain_candidates = [
            CandidateItem.of(
                product,
                float(c.price_per_kg),
                float(c.min_amount_g),
                float(c.max_amount_g),
            )
            for product, c in zip(products, candidates, strict=True)
        ]
        try:
            opt = optimize_cost(domain_candidates, reference, constraints)
        except OptimizationInfeasibleError as e:
            raise UnprocessableError(e.detail) from e

        amounts = opt["amounts"]
        enriched = [
            product.report_item(amount)
            for product, amount in zip(products, amounts, strict=True)
        ]
        return {
            "optimal_items": [
                {
                    "product_id": c.product_id,
                    "amount_g": amount,
                    "price_per_kg": c.price_per_kg,
                }
                for c, amount in zip(domain_candidates, amounts, strict=True)
            ],
            # `total_cost_per_100g` устарело: оставлено для выпущенных клиентов.
            "total_cost_per_100g": opt["total_cost_per_100g"],
            "total_cost_per_kg": opt["total_cost_per_100g"] * PER_KILOGRAM,
            "report": compute_report(enriched, reference),
        }

    # --------------------------------------------- оптимизация состава
    async def optimize_composition(
        self,
        reference_protein_id: UUID,
        items: list[CompositionItemInput],
        mode: str,
    ) -> dict:
        reference = await self._reference(reference_protein_id)
        products = await self._products_for([item.product_id for item in items])
        candidates = [
            CandidateItem.of(
                product,
                item.price_per_kg or 0.0,
                item.min_amount_g,
                item.max_amount_g,
            )
            for product, item in zip(products, items, strict=True)
        ]
        try:
            result = await asyncio.to_thread(
                optimize_recipe,
                candidates,
                reference,
                [item.amount_g for item in items],
                mode,
            )
        except RecipeOptimizationError as exc:
            raise UnprocessableError({"code": exc.code, "message": str(exc)}) from exc
        for output, source in zip(result["optimal_items"], items, strict=True):
            output["price_per_kg"] = source.price_per_kg
        return result
