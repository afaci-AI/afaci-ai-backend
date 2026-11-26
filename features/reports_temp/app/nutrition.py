"""TEMP: reports_temp — урезанный расчёт пищевой ценности рецептуры (учебная ветка).

Сокращённая версия полного расчёта калькулятора (`compute_report`): оставлены
макросостав, энергоценность и аминокислотный скор. Формулы берутся из калькулятора.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.errors import BadRequestError
from features.calculator.domain.formulas.amino import (
    amino_contributors,
    amino_rows,
    protein_base,
)
from features.calculator.domain.formulas.macro import energy_kcal, macro_composition

EMPTY_RECIPE = "В рецептуре нет ингредиентов с массой."


@dataclass(frozen=True)
class AminoScore:
    name: str
    score: float | None


@dataclass(frozen=True)
class RecipeNutrition:
    mass_g: float
    protein: float
    fat: float
    carb: float
    energy_kcal: float | None
    scores: list[AminoScore]
    limiting: AminoScore | None


def recipe_nutrition(items: list[dict], reference: dict) -> RecipeNutrition:
    """Пищевая ценность 100 г рецептуры; шаги выполняются строго по порядку.

    items: [{name, amount_g, chem: {"Массовая доля белка": x, ...}, amino: {...}}]
    reference: {name, values: {"ИЗО": 4.0, ...}}
    """
    # 1. Проверить рецептуру: нужен хотя бы один ингредиент с массой.
    used = [it for it in items if it["amount_g"] > 0]
    if not used:
        raise BadRequestError(EMPTY_RECIPE)

    # 2. Масса рецептуры, г.
    mass_g = sum(it["amount_g"] for it in used)

    # 3. Белок, жир, углеводы: S = Σ(Sᵢ·Xᵢ) / 100.
    macro = macro_composition(used)

    # 4. Энергоценность: ЭЦ = 4·Б + 9·Ж + 4·У.
    energy = energy_kcal(macro["protein"], macro["fat"], macro["carb"])

    # 5. Аминокислотный скор по эталону: C = Mⱼ / эталон · 100.
    contributors = amino_contributors(used)
    rows = amino_rows(contributors, protein_base(contributors), reference)
    scores = [AminoScore(r["name"], r["score"]) for r in rows]

    # 6. Лимитирующая аминокислота — с наименьшим скором.
    known = [s for s in scores if s.score is not None]
    limiting = min(known, key=lambda s: s.score) if known else None

    return RecipeNutrition(
        mass_g=mass_g,
        protein=macro["protein"],
        fat=macro["fat"],
        carb=macro["carb"],
        energy_kcal=energy,
        scores=scores,
        limiting=limiting,
    )
