"""Формулы методики Липатова — единственное место расчётов (см. report.py)."""

from .constants import NAK_GROUPS, REQUIRED_SUM, SUM_TOLERANCE
from .report import compute_report

__all__ = ["NAK_GROUPS", "REQUIRED_SUM", "SUM_TOLERANCE", "compute_report"]
