"""Этапы 1 и 3: макросостав рецептуры и энергетическая ценность."""

from __future__ import annotations

from domain.products.daily_norms import energy_kcal

from .constants import CARB, FAT, FIBER, PROTEIN


def _macro(items: list[dict], name: str) -> float:
    return sum(it["chem"].get(name, 0.0) * it["amount_g"] for it in items) / 100.0


def macro_composition(items: list[dict]) -> dict:
    """S = Σ(Sᵢ·Xᵢ) / 100 по белку, жиру, углеводам, волокнам; ЭЦ = 4·Б + 9·Ж + 4·У."""
    protein = _macro(items, PROTEIN)
    fat = _macro(items, FAT)
    carb = _macro(items, CARB)
    fiber = _macro(items, FIBER)
    return {
        "protein": protein,
        "fat": fat,
        "carb": carb,
        "fiber": fiber,
        "energy": energy_kcal(protein, fat, carb),
    }
