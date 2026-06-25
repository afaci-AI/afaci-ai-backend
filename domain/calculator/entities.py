from dataclasses import dataclass, field
from typing import Optional


@dataclass
class RecipeItem:
    product_id: str
    amount_g: float


@dataclass
class AminoAcidRow:
    name: str
    m_j: float
    reference: Optional[float]
    score: Optional[float]
    utility: Optional[float]
    is_limiting: bool
    is_min: bool


@dataclass
class ComputeResult:
    recipe: list
    sum_g: float
    reference: dict
    macro: dict
    energy_kcal: float
    amino_acids: list
    c_min: Optional[dict]
    limiting: list
    limiting_count: int
    quality: dict
    amino_contributors: list
    warnings: list
    verdict: Optional[dict]
