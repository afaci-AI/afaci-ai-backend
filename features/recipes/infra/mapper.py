"""Преобразование ORM-моделей рецептур в доменные сущности и обратно."""

from __future__ import annotations

from core.db.models import RecipeGroup as GroupRow
from core.db.models import SavedRecipe as RecipeRow
from core.db.models import SavedRecipeItem as ItemRow

from ..domain import Recipe, RecipeGroup, RecipeItem, RecipeMetrics


def to_group(row: GroupRow) -> RecipeGroup:
    return RecipeGroup(id=row.id, name=row.name, created_at=row.created_at)


def to_recipe(row: RecipeRow, *, with_items: bool) -> Recipe:
    items = (
        [
            RecipeItem(
                product_id=it.product_id,
                amount_g=it.amount_g,
                sort_order=it.sort_order,
                price_per_kg=it.price_per_kg,
            )
            for it in row.items
        ]
        if with_items
        else []
    )
    return Recipe(
        id=row.id,
        name=row.name,
        group_id=row.group_id,
        reference_protein_id=row.reference_protein_id,
        metrics=RecipeMetrics(
            bc=row.bc,
            kras=row.kras,
            u=row.u_coef,
            g=row.g_coef,
            energy_kcal=row.energy_kcal,
            c_min_name=row.c_min_name,
            c_min_score=row.c_min_score,
        ),
        items=items,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def apply_metrics(row: RecipeRow, metrics: RecipeMetrics) -> None:
    row.bc = metrics.bc
    row.kras = metrics.kras
    row.u_coef = metrics.u
    row.g_coef = metrics.g
    row.energy_kcal = metrics.energy_kcal
    row.c_min_name = metrics.c_min_name
    row.c_min_score = metrics.c_min_score


def to_item_row(item: RecipeItem) -> ItemRow:
    return ItemRow(
        product_id=item.product_id,
        amount_g=item.amount_g,
        sort_order=item.sort_order,
        price_per_kg=item.price_per_kg,
    )
