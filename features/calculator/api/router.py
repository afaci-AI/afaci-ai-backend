"""
Эндпоинты Калькулятора пищевой и биологической ценности.

  GET  /api/v1/calculator/reference-proteins  — эталоны ФАО/ВОЗ (для селектора и Табл. 4)
  GET  /api/v1/calculator/recipes             — сохранённые рецептуры (загружаемые примеры)
  POST /api/v1/calculator/compute             — расчёт по списку ингредиентов + эталону
  POST /api/v1/calculator/optimize-cost       — оптимизация стоимости рецептуры (ЛП, libs/lp)
  POST /api/v1/calculator/optimize-recipe     — оптимизация относительно исходного состава
"""

from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Depends

from core.db.models import User
from core.security import get_current_user

from ..app import CompositionReport, RecipeCalculator, ReferenceCatalog
from ..app.ports import ReferenceEntry
from .deps import (
    PdfUrl,
    get_calculator,
    get_composition_report,
    get_pdf_url,
    get_reference_catalog,
)
from .schemas import (
    CalcRequest,
    OptimizeCostRequest,
    OptimizeRecipeRequest,
    ReferenceProteinOut,
    ReferenceSourceOut,
)

TAG = "Calculator"
router = APIRouter(prefix="/api/v1/calculator", tags=[TAG])


def _source_out(entry: ReferenceEntry, pdf_url: PdfUrl) -> ReferenceSourceOut | None:
    source = entry.source
    if source is None:
        return None
    return ReferenceSourceOut(
        title=source.title,
        authors=source.authors,
        year=source.year,
        location=source.location,
        url=source.url,
        pdf_url=pdf_url(entry.source_pdf_filename),
    )


def _reference_out(entry: ReferenceEntry, pdf_url: PdfUrl) -> ReferenceProteinOut:
    return ReferenceProteinOut(
        id=entry.id,
        name=entry.name,
        year=entry.year,
        is_default=entry.is_default,
        description=entry.description,
        values=[asdict(value) for value in entry.values],
        source=_source_out(entry, pdf_url),
    )


@router.get("/reference-proteins", summary="Эталонные белки ФАО/ВОЗ")
async def list_reference_proteins(
    pdf_url: Annotated[PdfUrl, Depends(get_pdf_url)],
    catalog: Annotated[ReferenceCatalog, Depends(get_reference_catalog)],
) -> list[ReferenceProteinOut]:
    return [
        _reference_out(entry, pdf_url)
        for entry in await catalog.list_reference_proteins()
    ]


@router.get("/recipes", summary="Сохранённые рецептуры (примеры)")
async def list_recipes(
    catalog: Annotated[ReferenceCatalog, Depends(get_reference_catalog)],
):
    return [asdict(recipe) for recipe in await catalog.list_example_recipes()]


# --------------------------- расчёт ------------------------------
@router.post("/compute", summary="Рассчитать пищевую и биологическую ценность")
async def compute(
    req: CalcRequest,
    report: Annotated[CompositionReport, Depends(get_composition_report)],
    _user: Annotated[User, Depends(get_current_user)],
):
    items = [{"product_id": it.product_id, "amount_g": it.amount_g} for it in req.items]
    return await report.compute(req.reference_protein_id, items)


@router.post("/optimize-cost", summary="Оптимизировать стоимость рецептуры")
async def optimize_cost_endpoint(
    req: OptimizeCostRequest,
    calculator: Annotated[RecipeCalculator, Depends(get_calculator)],
    _user: Annotated[User, Depends(get_current_user)],
):
    """
    Находит дешевейший состав рецептуры при ограничениях на качество белка (БЦ, КРАС).
    Возвращает 422 с описанием, если задача неразрешима.
    """
    candidates = [
        {
            "product_id": str(c.product_id),
            "price_per_kg": c.price_per_kg,
            "min_amount_g": c.min_amount_g,
            "max_amount_g": c.max_amount_g,
        }
        for c in req.candidates
    ]
    constraints = {
        "bc_min": req.constraints.bc_min,
        "kras_max": req.constraints.kras_max,
    }
    return await calculator.optimize_cost(
        req.reference_protein_id, candidates, constraints
    )


@router.post(
    "/optimize-recipe",
    summary="Оптимизировать рецептуру относительно исходного состава",
)
async def optimize_recipe_endpoint(
    req: OptimizeRecipeRequest,
    calculator: Annotated[RecipeCalculator, Depends(get_calculator)],
    _user: Annotated[User, Depends(get_current_user)],
):
    return await calculator.optimize_composition(
        req.reference_protein_id,
        [
            {**item.model_dump(), "product_id": str(item.product_id)}
            for item in req.items
        ],
        req.mode,
    )
