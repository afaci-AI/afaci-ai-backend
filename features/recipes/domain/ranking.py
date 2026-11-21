"""Ранжирование рецептур по БЦ, КРАС, U и G с весами показателей."""

from __future__ import annotations

from dataclasses import dataclass

from .entities import Recipe


@dataclass
class RankingWeights:
    bc: float = 0.25
    kras: float = 0.25
    utility: float = 0.25
    g: float = 0.25


def normalize(values: list[float | None], higher_is_better: bool) -> list[float]:
    """Нормировка показателя по выборке в [0..1]. None и нулевой разброс → нейтрально."""
    present = [v for v in values if v is not None]
    if not present:
        return [0.0 for _ in values]
    lo, hi = min(present), max(present)
    span = hi - lo
    out: list[float] = []
    for v in values:
        if v is None:
            out.append(0.0)
        elif span == 0:
            out.append(1.0)
        else:
            n = (v - lo) / span
            out.append(n if higher_is_better else 1.0 - n)
    return out


def _normalized_weights(w: RankingWeights) -> dict:
    wsum = (w.bc + w.kras + w.utility + w.g) or 1.0
    return {
        "bc": w.bc / wsum,
        "kras": w.kras / wsum,
        "u": w.utility / wsum,
        "v": w.utility / wsum,  # устаревший псевдоним u
        "g": w.g / wsum,
    }


def rank_recipes(
    recipes: list[Recipe], group_names: dict, weights: RankingWeights
) -> dict:
    wn = _normalized_weights(weights)
    n_bc = normalize([r.metrics.bc for r in recipes], higher_is_better=True)
    n_kras = normalize([r.metrics.kras for r in recipes], higher_is_better=False)
    n_u = normalize([r.metrics.u for r in recipes], higher_is_better=True)
    n_g = normalize([r.metrics.g for r in recipes], higher_is_better=False)

    results = []
    for i, r in enumerate(recipes):
        composite = (
            wn["bc"] * n_bc[i]
            + wn["kras"] * n_kras[i]
            + wn["u"] * n_u[i]
            + wn["g"] * n_g[i]
        )
        results.append(
            {
                "recipe_id": str(r.id),
                "name": r.name,
                "group": group_names.get(r.group_id) if r.group_id else None,
                "bc": r.metrics.bc,
                "kras": r.metrics.kras,
                "U": r.metrics.u,
                "V": r.metrics.u,  # устаревший псевдоним U
                "G": r.metrics.g,
                "normalized": {
                    "bc": round(n_bc[i], 4),
                    "kras": round(n_kras[i], 4),
                    "U": round(n_u[i], 4),
                    "V": round(n_u[i], 4),  # устаревший псевдоним U
                    "G": round(n_g[i], 4),
                },
                "composite": round(composite, 4),
            }
        )

    results.sort(key=lambda x: x["composite"], reverse=True)
    for rank, item in enumerate(results, start=1):
        item["rank"] = rank

    return {
        "weights": wn,
        "winner": results[0]["recipe_id"] if results else None,
        "ranking": results,
    }
