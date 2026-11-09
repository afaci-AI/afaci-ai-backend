"""Предупреждения о неполных данных рецептуры."""

from __future__ import annotations

from .constants import MACRO_LABELS, PROTEIN


def missing_amino_protein(items: list[dict]) -> list[str]:
    """Белоксодержащие ингредиенты без данных по НАК."""
    return [
        it["name"]
        for it in items
        if not it.get("amino") and it["chem"].get(PROTEIN, 0.0) > 0
    ]


def ingredient_warnings(items: list[dict], no_amino_protein: list[str]) -> list[str]:
    warnings: list[str] = []
    if no_amino_protein:
        warnings.append(
            "В аминокислотном расчёте не учтены ингредиенты без данных по НАК "
            "(вклад в макросостав сохранён): " + ", ".join(no_amino_protein) + "."
        )

    missing_chem = []
    for it in items:
        if it["amount_g"] <= 0:
            continue
        missing = [
            label for key, label in MACRO_LABELS.items() if key not in it["chem"]
        ]
        if missing:
            missing_chem.append(f"{it['name']} ({', '.join(missing)})")
    if missing_chem:
        warnings.append(
            "Отсутствуют данные химического состава: "
            + "; ".join(missing_chem)
            + ". Макросостав и энергетическая ценность рассчитаны только по известным "
            "данным; отсутствие значения не означает нулевое содержание."
        )
    return warnings
