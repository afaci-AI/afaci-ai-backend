"""Этап 2: НАК суммарного белка и аминокислотный скор."""

from __future__ import annotations

from .constants import NAK_GROUPS, PROTEIN


def protein_base(items: list[dict]) -> float:
    """Σ(белокᵢ·Xᵢ) по переданным ингредиентам."""
    return sum(it["chem"].get(PROTEIN, 0.0) * it["amount_g"] for it in items)


def amino_contributors(items: list[dict]) -> list[dict]:
    """Вклад в белок учитывают только ингредиенты, у которых есть данные по НАК."""
    return [it for it in items if it.get("amino")]


def amino_rows(contributors: list[dict], base: float, reference: dict) -> list[dict]:
    """Строки по группам НАК: Mⱼ, значение эталона и скор C = Mⱼ/эталон·100."""
    rows: list[dict] = []
    if not (contributors and base > 0):
        return rows
    for group, members in NAK_GROUPS:
        # Mⱼ = Σ(белокᵢ·Xᵢ·Mᵢⱼ) / Σ(белокᵢ·Xᵢ),  Mᵢⱼ = мг_группы / (белок%·10)
        numerator = 0.0
        for it in contributors:
            p = it["chem"].get(PROTEIN, 0.0)
            if p <= 0:
                continue
            group_mg = sum(it["amino"].get(m, 0.0) for m in members)
            m_ij = group_mg / (p * 10.0)  # г/100 г белка
            numerator += p * it["amount_g"] * m_ij
        m_j = numerator / base
        ref_val = reference["values"].get(group)
        score = (m_j / ref_val * 100.0) if ref_val else None
        rows.append({"name": group, "m_j": m_j, "reference": ref_val, "score": score})
    return rows
