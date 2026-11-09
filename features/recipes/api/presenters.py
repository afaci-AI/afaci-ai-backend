"""Представление сущностей рецептур в ответах API (формат не менялся)."""

from __future__ import annotations

from ..domain import Recipe, RecipeGroup


def group_public(g: RecipeGroup, count: int = 0) -> dict:
    return {
        "id": str(g.id),
        "name": g.name,
        "created_at": g.created_at.isoformat() if g.created_at else None,
        "recipe_count": count,
    }


def recipe_public(r: Recipe, with_items: bool = False) -> dict:
    m = r.metrics
    data = {
        "id": str(r.id),
        "name": r.name,
        "group_id": str(r.group_id) if r.group_id else None,
        "reference_protein_id": str(r.reference_protein_id),
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
        "metrics": {
            "bc": m.bc,
            "kras": m.kras,
            "U": m.u,
            "V": m.u,  # устаревший псевдоним U
            "G": m.g,
            "energy_kcal": m.energy_kcal,
            "c_min_name": m.c_min_name,
            "c_min_score": m.c_min_score,
        },
    }
    if with_items:
        data["items"] = [
            {
                "product_id": str(it.product_id),
                "amount_g": it.amount_g,
                "sort_order": it.sort_order,
                "price_per_kg": it.price_per_kg,
            }
            for it in r.sorted_items()
        ]
    return data
