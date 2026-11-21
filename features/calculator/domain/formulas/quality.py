"""Этап 4: качественные показатели белка (КРАС, БЦ, U, G) и лимитирующие НАК."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Quality:
    c_min: float | None = None
    c_min_name: str | None = None
    kras: float | None = None
    bc: float | None = None
    util_u: float | None = None
    util_g: float | None = None


def quality_indicators(rows: list[dict]) -> Quality:
    """КРАС = Σ(Cⱼ−Cmin)/n, БЦ = 100−КРАС, αⱼ = Cmin/Cⱼ,
    U = Σ(αⱼ·Aⱼ)/ΣAⱼ, G = Σ(Aⱼ·(1−αⱼ)) / (Cmin/100).

    Дополняет строки полями `utility`, `is_limiting`, `is_min`.
    """
    scored = [r for r in rows if r["score"] is not None]
    c_min = min((r["score"] for r in scored), default=None)
    c_min_name = next((r["name"] for r in scored if r["score"] == c_min), None)

    result = Quality(c_min=c_min, c_min_name=c_min_name)
    if scored and c_min is not None:
        result.kras = sum(r["score"] - c_min for r in scored) / len(scored)
        result.bc = 100.0 - result.kras

        sum_alpha_a = 0.0
        sum_a = 0.0
        sum_excess = 0.0
        for r in scored:
            alpha = c_min / r["score"] if r["score"] else 0.0
            r["utility"] = alpha
            a = r["m_j"]
            sum_alpha_a += alpha * a
            sum_a += a
            sum_excess += a * (1 - alpha)
        result.util_u = sum_alpha_a / sum_a if sum_a else None
        result.util_g = sum_excess / (c_min / 100.0) if c_min else None

    # Пометить лимитирующие и минимальную НАК
    for r in rows:
        r["is_limiting"] = r["score"] is not None and r["score"] < 100
        r["is_min"] = r["name"] == c_min_name
    return result
