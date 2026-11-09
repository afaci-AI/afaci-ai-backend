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

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.v1.reference_documents import document_path
from application.products.daily_norms_service import (
    daily_norms_payload,
    load_sources,
    product_amounts,
)
from core.db.session import get_db

TAG = "Sources and daily norms"
router = APIRouter(prefix="/api/v1", tags=[TAG])


class SourceOut(BaseModel):
    id: str
    kind: str
    title: str
    authors: str | None = None
    year: int | None = None
    location: str | None = None
    url: str | None = None
    pdf_url: str | None = None
    used_for: str | None = None


class NormRowOut(BaseModel):
    key: str
    name: str
    unit: str
    norm: float
    amount: float | None = None
    percent: float | None = None
    source_id: str | None = None
    basis: str | None = None


class NormsInfoOut(BaseModel):
    title: str
    paragraphs: list[str]
    disclaimer: str


class DailyNormsOut(BaseModel):
    norms: list[NormRowOut]
    sources: list[SourceOut]
    info: NormsInfoOut


def pdf_url_builder(request: Request):
    """Ссылка на локально хранимый PDF источника или None, если файла нет."""

    def build(filename: str | None) -> str | None:
        if filename and document_path(filename) is not None:
            return str(request.url_for("get_reference_document", filename=filename))
        return None

    return build


@router.get("/sources", summary="Источники информации")
async def list_sources(
    request: Request, db: Annotated[AsyncSession, Depends(get_db)]
) -> list[SourceOut]:
    return [
        SourceOut(**source)
        for source in await load_sources(db, pdf_url_builder(request))
    ]


@router.get("/daily-norms", summary="Усреднённые суточные нормы")
async def get_daily_norms(
    request: Request, db: Annotated[AsyncSession, Depends(get_db)]
) -> DailyNormsOut:
    return DailyNormsOut(**await daily_norms_payload(db, pdf_url_builder(request)))


@router.get(
    "/products/{id}/daily-norms",
    summary="Суточные нормы и доля от нормы для 100 г продукта",
)
async def get_product_daily_norms(
    id: UUID, request: Request, db: Annotated[AsyncSession, Depends(get_db)]
) -> DailyNormsOut:
    amounts = await product_amounts(db, id)
    if amounts is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return DailyNormsOut(
        **await daily_norms_payload(db, pdf_url_builder(request), amounts)
    )
