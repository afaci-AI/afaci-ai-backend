"""Этапы 1 и 3: макросостав рецептуры и энергетическая ценность."""

from __future__ import annotations

from .constants import CARB, FAT, FIBER, PROTEIN

# Коэффициенты МР 2.3.1.0253-21, приложение 3: белки 4,0, жиры 9,0, углеводы 4,0 ккал/г.
KCAL_PER_G_PROTEIN = 4
KCAL_PER_G_FAT = 9
KCAL_PER_G_CARB = 4


def energy_kcal(
    protein: float | None, fat: float | None, carb: float | None
) -> float | None:
    """Энергия, ккал на 100 г; None, если неизвестен хотя бы один макронутриент."""
    if protein is None or fat is None or carb is None:
        return None
    return KCAL_PER_G_PROTEIN * protein + KCAL_PER_G_FAT * fat + KCAL_PER_G_CARB * carb


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
