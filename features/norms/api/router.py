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

from fastapi import APIRouter, Depends, Request

from ..app import NormsService
from .deps import get_norms_service
from .documents import pdf_url_builder
from .schemas import DailyNormsOut, SourceOut

TAG = "Sources and daily norms"
router = APIRouter(prefix="/api/v1", tags=[TAG])


@router.get("/sources", summary="Источники информации")
async def list_sources(
    request: Request, norms: Annotated[NormsService, Depends(get_norms_service)]
) -> list[SourceOut]:
    return [
        SourceOut(**source) for source in await norms.sources(pdf_url_builder(request))
    ]


@router.get("/daily-norms", summary="Усреднённые суточные нормы")
async def get_daily_norms(
    request: Request, norms: Annotated[NormsService, Depends(get_norms_service)]
) -> DailyNormsOut:
    return DailyNormsOut(**await norms.payload(pdf_url_builder(request)))


@router.get(
    "/products/{id}/daily-norms",
    summary="Суточные нормы и доля от нормы для 100 г продукта",
)
async def get_product_daily_norms(
    id: UUID,
    request: Request,
    norms: Annotated[NormsService, Depends(get_norms_service)],
) -> DailyNormsOut:
    return DailyNormsOut(**await norms.product_payload(id, pdf_url_builder(request)))
