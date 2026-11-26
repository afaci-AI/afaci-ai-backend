"""Сборка зависимостей калькулятора: порты → SQL-реализация (composition root)."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.session import get_db
from features.norms.api.deps import get_norms_service, get_pdf_url
from features.norms.api.presenters import PdfUrl, present_payload
from features.norms.app import CompositionEntry, NormsService

from ..app import CompositionReport, RecipeCalculator, ReferenceCatalog
from ..infra.sql_reader import SqlCalculatorData

__all__ = [
    "PdfUrl",
    "get_calculator",
    "get_composition_report",
    "get_pdf_url",
    "get_reference_catalog",
]


class _DailyNormsAdapter:
    """Суточные нормы считает фича норм через её публичный сервис.

    Строки состава отчёта переводятся в записи норм, а ссылки на PDF источников
    строит презентер норм — так же, как в её собственных эндпоинтах.
    """

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
        payload = await self._norms.recipe_payload(
            macro,
            energy_kcal,
            [CompositionEntry.of(row) for row in micro],
            [CompositionEntry.of(row) for row in other],
        )
        return present_payload(payload, self._pdf_url)


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
