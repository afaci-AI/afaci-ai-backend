"""Формулы методики Липатова — единственное место расчётов (см. report.py)."""

from .constants import NAK_GROUPS, REQUIRED_SUM, SUM_TOLERANCE
from .macro import (
    KCAL_PER_G_CARB,
    KCAL_PER_G_FAT,
    KCAL_PER_G_PROTEIN,
    energy_kcal,
)
from .report import compute_report

__all__ = [
    "KCAL_PER_G_CARB",
    "KCAL_PER_G_FAT",
    "KCAL_PER_G_PROTEIN",
    "NAK_GROUPS",
    "REQUIRED_SUM",
    "SUM_TOLERANCE",
    "compute_report",
    "energy_kcal",
]
