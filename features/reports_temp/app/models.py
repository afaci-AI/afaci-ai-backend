"""Данные отчётов: критерии выборки и готовый к выводу документ (не зависит от PDF)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

# Верхние границы выборок (решено 2026-11-12).
MAX_LIST_ROWS = 500
MAX_TOP = 100


@dataclass(frozen=True)
class ListCriteria:
    category: str | None = None
    subcategory: str | None = None
    region: str | None = None
    name: str | None = None


@dataclass(frozen=True)
class RankingCriteria:
    nutrient: str
    order: Literal["desc", "asc"] = "desc"
    top: int = 20
    category: str | None = None


@dataclass
class ReportTable:
    columns: list[str]
    rows: list[list[str]]
    # Относительная ширина колонок и выравнивание ("L" или "R").
    widths: list[float]
    align: list[str]


@dataclass
class ReportSection:
    title: str | None
    table: ReportTable


@dataclass
class ReportDocument:
    title: str
    author: str
    created_at: datetime
    criteria: list[tuple[str, str]]
    sections: list[ReportSection] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    empty_message: str | None = None
    filename: str = "report.pdf"
