"""Показатели рецептуры из отчёта калькулятора."""

from __future__ import annotations

from .entities import RecipeMetrics


def metrics_from_report(report: dict) -> RecipeMetrics:
    quality = report.get("quality") or {}
    c_min = report.get("c_min") or {}
    return RecipeMetrics(
        bc=quality.get("bc"),
        kras=quality.get("kras"),
        u=quality.get("U"),
        g=quality.get("G"),
        energy_kcal=report.get("energy_kcal"),
        c_min_name=c_min.get("name"),
        c_min_score=c_min.get("score"),
    )
