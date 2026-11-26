"""Сборка зависимостей калькулятора: порты → SQL-реализация (composition root)."""

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.session import get_db
from features.norms.api.deps import get_norms_service
from features.norms.api.documents import pdf_url_builder
from features.norms.app import NormsService

from ..app import CompositionReport, RecipeCalculator, ReferenceCatalog
from ..infra.sql_reader import SqlCalculatorData

PdfUrl = Callable[[str | None], str | None]


class _DailyNormsAdapter:
    """Суточные нормы считает фича норм через её публичный сервис."""

    def __init__(self, norms: NormsService, pdf_url: PdfUrl) -> None:
        self._norms = norms
        self._pdf_url = pdf_url

    async def for_recipe(
        self,
        *,
        macro: dict[str, float | None],
        energy_kcal: float | None,
        micro: list[dict],
        other: list[dict],
    ) -> dict:
        return await self._norms.recipe_payload(
            self._pdf_url, macro, energy_kcal, micro, other
        )


def get_pdf_url(request: Request) -> PdfUrl:
    """Ссылка на локально хранимый PDF источника или None, если файла нет."""
    return pdf_url_builder(request)


async def get_calculator(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RecipeCalculator:
    data = SqlCalculatorData(db)
    return RecipeCalculator(references=data, products=data)


async def get_composition_report(
    calculator: Annotated[RecipeCalculator, Depends(get_calculator)],
    norms: Annotated[NormsService, Depends(get_norms_service)],
    pdf_url: Annotated[PdfUrl, Depends(get_pdf_url)],
) -> CompositionReport:
    return CompositionReport(calculator, _DailyNormsAdapter(norms, pdf_url))


async def get_reference_catalog(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ReferenceCatalog:
    return SqlCalculatorData(db)
