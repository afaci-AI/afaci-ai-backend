"""
Реестр источников и суточные нормы.

  GET /api/v1/sources                       — все источники, на которые опирается программа
  GET /api/v1/daily-norms                   — усреднённые суточные нормы с источником и пояснением
  GET /api/v1/products/{id}/daily-norms     — нормы и доля от нормы для 100 г продукта

Нормы и доля от нормы считаются на backend; доля рецептуры возвращается в ответе
`POST /api/v1/calculator/compute` (поле `daily_norms`).
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from ..app import NormsService
from .deps import get_norms_service, get_pdf_url
from .presenters import PdfUrl, present_payload, source_out
from .schemas import DailyNormsOut, SourceOut

TAG = "Sources and daily norms"
router = APIRouter(prefix="/api/v1", tags=[TAG])

Norms = Annotated[NormsService, Depends(get_norms_service)]
PdfLinks = Annotated[PdfUrl, Depends(get_pdf_url)]


@router.get("/sources", summary="Источники информации")
async def list_sources(norms: Norms, pdf_url: PdfLinks) -> list[SourceOut]:
    return [SourceOut(**source_out(s, pdf_url)) for s in await norms.sources()]


@router.get("/daily-norms", summary="Усреднённые суточные нормы")
async def get_daily_norms(norms: Norms, pdf_url: PdfLinks) -> DailyNormsOut:
    return DailyNormsOut(**present_payload(await norms.payload(), pdf_url))


@router.get(
    "/products/{id}/daily-norms",
    summary="Суточные нормы и доля от нормы для 100 г продукта",
)
async def get_product_daily_norms(
    id: UUID, norms: Norms, pdf_url: PdfLinks
) -> DailyNormsOut:
    return DailyNormsOut(**present_payload(await norms.product_payload(id), pdf_url))
