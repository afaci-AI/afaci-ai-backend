"""TEMP: reports_temp — PDF-отчёты по выборке сырья и пищевой ценности рецептуры."""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Annotated, Literal
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response

from core.db.models import User
from core.security import get_current_user

from ..app import (
    MAX_TOP,
    ListCriteria,
    RankingCriteria,
    ReportDocument,
    ReportService,
)
from .deps import get_pdf_renderer, get_report_service

TAG = "Temporary reports"

router = APIRouter(prefix="/api/v1/reports-temp", tags=[TAG])

Service = Annotated[ReportService, Depends(get_report_service)]
Renderer = Annotated[Callable[[ReportDocument], bytes], Depends(get_pdf_renderer)]
CurrentUser = Annotated[User, Depends(get_current_user)]


def _pdf(
    render: Callable[[ReportDocument], bytes], doc: ReportDocument, attachment: bool
) -> Response:
    disposition = "attachment" if attachment else "inline"
    return Response(
        render(doc),
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f"{disposition}; filename*=UTF-8''{quote(doc.filename)}"
            )
        },
    )


@router.get(
    "/options",
    summary="Значения для формы отчётов",
    description="Категории, подкатегории, регионы и нутриенты (с единицами).",
)
async def report_options(service: Service, _user: CurrentUser):
    return await service.options()


@router.get(
    "/products/lookup",
    summary="Подбор продукта для карточки",
    description="До 20 продуктов, в названии которых есть часть строки `name`.",
)
async def lookup_products(
    service: Service,
    _user: CurrentUser,
    name: Annotated[str, Query(min_length=1, max_length=200)],
):
    return await service.lookup(name)


@router.get(
    "/recipes",
    summary="Сохранённые рецептуры для отчёта о пищевой ценности",
    description="Рецептуры текущего пользователя: id и название.",
)
async def report_recipes(service: Service, user: CurrentUser):
    return await service.recipes(str(user.id))


@router.get(
    "/recipes/{recipe_id}/nutrition.pdf",
    summary="PDF: пищевая ценность рецептуры",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}}},
)
async def recipe_nutrition_pdf(
    recipe_id: UUID,
    service: Service,
    render: Renderer,
    user: CurrentUser,
    download: bool = False,
):
    doc = await service.nutrition_report(
        str(recipe_id), str(user.id), user.name, datetime.now(UTC)
    )
    return _pdf(render, doc, download)


@router.get(
    "/products.pdf",
    summary="PDF: перечень сырья",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}}},
)
async def products_pdf(
    service: Service,
    render: Renderer,
    user: CurrentUser,
    category: Annotated[str | None, Query(max_length=200)] = None,
    subcategory: Annotated[str | None, Query(max_length=200)] = None,
    region: Annotated[str | None, Query(max_length=200)] = None,
    name: Annotated[str | None, Query(max_length=200)] = None,
    download: bool = False,
):
    doc = await service.products_report(
        ListCriteria(category, subcategory, region, name),
        user.name,
        datetime.now(UTC),
    )
    return _pdf(render, doc, download)


@router.get(
    "/ranking.pdf",
    summary="PDF: рейтинг сырья по нутриенту",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}}},
)
async def ranking_pdf(
    service: Service,
    render: Renderer,
    user: CurrentUser,
    nutrient: Annotated[str, Query(min_length=1, max_length=200)],
    order: Literal["desc", "asc"] = "desc",
    top: Annotated[int, Query(ge=1, le=MAX_TOP)] = 20,
    category: Annotated[str | None, Query(max_length=200)] = None,
    download: bool = False,
):
    doc = await service.ranking_report(
        RankingCriteria(nutrient, order, top, category), user.name, datetime.now(UTC)
    )
    return _pdf(render, doc, download)


@router.get(
    "/products/{product_id}.pdf",
    summary="PDF: карточка сырья",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}}},
)
async def product_card_pdf(
    product_id: UUID,
    service: Service,
    render: Renderer,
    user: CurrentUser,
    download: bool = False,
):
    doc = await service.card_report(str(product_id), user.name, datetime.now(UTC))
    return _pdf(render, doc, download)
