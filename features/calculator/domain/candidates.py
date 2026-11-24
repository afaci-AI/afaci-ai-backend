"""Кандидаты оптимизации: ингредиент с ценой и допустимым диапазоном долей."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .entities import ProductNutrients


@dataclass
class CandidateItem:
    product_id: str
    name: str
    chem: dict
    amino: dict
    price_per_kg: float
    min_amount_g: float = 0.0
    max_amount_g: float = 100.0
    region: str | None = None
    subcategory: str | None = None

    @classmethod
    def of(
        cls, product: ProductNutrients, price: float, low: float, high: float
    ) -> CandidateItem:
        return cls(
            product_id=product.product_id,
            name=product.name,
            chem=product.chem,
            amino=product.amino,
            region=product.region,
            subcategory=product.subcategory,
            price_per_kg=price,
            min_amount_g=low,
            max_amount_g=high,
        )


@dataclass
class CostOptimizationConstraints:
    bc_min: float | None = None  # БЦ ≥ bc_min
    kras_max: float | None = None  # КРАС ≤ kras_max


def build_items(candidates: list[CandidateItem], x: np.ndarray) -> list[dict]:
    """Ингредиенты в формате `compute_report` для вектора долей `x`."""
    return [
        {
            "product_id": c.product_id,
            "name": c.name,
            "region": c.region,
            "subcategory": c.subcategory,
            "amount_g": float(x[i]),
            "chem": c.chem,
            "amino": c.amino,
        }
        for i, c in enumerate(candidates)
    ]
