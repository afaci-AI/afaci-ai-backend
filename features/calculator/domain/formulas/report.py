"""Полный отчёт по рецептуре (методика Липатова).

Чистая вычислительная логика — без обращения к БД. Этапы методики:
  1. Макросостав:        S = Σ(Sᵢ·Xᵢ) / 100                     — macro.py
  2. НАК и скор:         Mⱼ = Σ(Sᵢ·Xᵢ·Mᵢⱼ) / Σ(Sᵢ·Xᵢ), C = Mⱼ/эталон·100  — amino.py
  3. Энергоценность:     ЭЦ = 4·Б + 9·Ж + 4·У                   — macro.py
  4. Качество:           КРАС, БЦ, U, G                         — quality.py
"""

from __future__ import annotations

from .amino import amino_contributors, amino_rows, protein_base
from .constants import NAK_GROUPS
from .data_warnings import ingredient_warnings, missing_amino_protein
from .macro import macro_composition
from .quality import Quality, quality_indicators
from .verdict import build_verdict


def _round(value: float | None, digits: int) -> float | None:
    return None if value is None else round(value, digits)


def _recipe_rows(items: list[dict], display) -> list[dict]:
    return [
        {
            "product_id": it["product_id"],
            "name": it["name"],
            "region": it.get("region"),
            "subcategory": it.get("subcategory"),
            "amount_g": display(it["amount_g"], 2),
        }
        for it in items
    ]


def _reference_block(reference: dict) -> dict:
    return {
        "id": reference["id"],
        "name": reference["name"],
        "year": reference.get("year"),
        "description": reference.get("description"),
        "values": [
            {"amino_acid": g, "value": reference["values"].get(g)}
            for g, _ in NAK_GROUPS
        ],
    }


def _macro_block(macro: dict, display) -> dict:
    protein, fat = macro["protein"], macro["fat"]
    return {
        "protein": display(protein, 2),
        "fat": display(fat, 2),
        "carb": display(macro["carb"], 2),
        "fiber": display(macro["fiber"], 2),
        "protein_fat_ratio": display(fat / protein, 2) if protein else None,
    }


def _amino_block(rows: list[dict], display) -> list[dict]:
    return [
        {
            "name": r["name"],
            "m_j": display(r["m_j"], 2),
            "reference": r["reference"],
            "score": display(r["score"], 1),
            "utility": display(r.get("utility"), 2),
            "is_limiting": r["is_limiting"],
            "is_min": r["is_min"],
        }
        for r in rows
    ]


def _quality_blocks(q: Quality, display) -> tuple[dict, dict]:
    shown = {
        "kras": display(q.kras, 1),
        "bc": display(q.bc, 1),
        "U": display(q.util_u, 2),
        # Устаревший псевдоним U для выпущенных клиентов; будет удалён.
        "V": display(q.util_u, 2),
        "G": display(q.util_g, 2),
    }
    # Raw values support numerical comparison without treating display rounding
    # as evidence that the composition improved.
    precise = {
        "kras": q.kras,
        "bc": q.bc,
        "U": q.util_u,
        "V": q.util_u,  # устаревший псевдоним U
        "G": q.util_g,
    }
    return shown, precise


def compute_report(items: list[dict], reference: dict, *, rounded: bool = True) -> dict:
    """
    items: [{product_id, name, region, subcategory, amount_g,
             chem: {"Массовая доля белка": x, "Массовая доля жира": x,
                    "Углеводы": x, "Пищевые волокна": x},
             amino: {"Изолейцин": мг/100г, ...}}]
    reference: {id, name, year, description, values: {"ИЗО": 4.0, ...}}
    """

    def display(value: float | None, digits: int) -> float | None:
        return _round(value, digits) if rounded else value

    macro = macro_composition(items)
    contributors = amino_contributors(items)
    base = protein_base(contributors)
    rows = amino_rows(contributors, base, reference)
    quality = quality_indicators(rows)
    limiting = [r["name"] for r in rows if r["is_limiting"]]

    no_amino_protein = missing_amino_protein(items)
    total_base = protein_base(items)
    coverage = min(base / total_base, 1.0) if total_base > 0 else None
    verdict = build_verdict(
        rows,
        reference,
        quality,
        missing_amino=no_amino_protein,
        amino_coverage=coverage,
    )
    shown, precise = _quality_blocks(quality, display)

    return {
        "recipe": _recipe_rows(items, display),
        "sum_g": display(sum(it["amount_g"] for it in items), 2),
        "reference": _reference_block(reference),
        "macro": _macro_block(macro, display),
        "energy_kcal": display(macro["energy"], 1),
        "amino_acids": _amino_block(rows, display),
        "c_min": {"name": quality.c_min_name, "score": display(quality.c_min, 1)}
        if quality.c_min_name
        else None,
        "limiting": limiting,
        "limiting_count": len(limiting),
        "quality": shown,
        "quality_precise": precise,
        "amino_contributors": [it["name"] for it in contributors],
        "warnings": ingredient_warnings(items, no_amino_protein),
        "verdict": verdict,
    }
