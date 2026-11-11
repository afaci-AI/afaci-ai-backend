"""
Эндпоинты Калькулятора пищевой и биологической ценности.

  GET  /api/v1/calculator/reference-proteins  — эталоны ФАО/ВОЗ (для селектора и Табл. 4)
  GET  /api/v1/calculator/recipes             — сохранённые рецептуры (загружаемые примеры)
  POST /api/v1/calculator/compute             — расчёт по списку ингредиентов + эталону
  POST /api/v1/calculator/optimize-cost       — оптимизация стоимости рецептуры (SLSQP)
  POST /api/v1/calculator/optimize-recipe     — оптимизация относительно исходного состава
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from core.db.models import User
from core.security import get_current_user
from features.norms.api.deps import get_norms_service
from features.norms.api.documents import document_path, pdf_url_builder
from features.norms.app import NormsService
from features.norms.domain.daily_norms import amounts_from_macros

from ..app import RecipeCalculator, ReferenceCatalog
from .deps import get_calculator, get_reference_catalog
from .schemas import (
    CalcRequest,
    OptimizeCostRequest,
    OptimizeRecipeRequest,
    ReferenceProteinOut,
    ReferenceSourceOut,
)

TAG = "Calculator"
router = APIRouter(prefix="/api/v1/calculator", tags=[TAG])


def _source_out(source: dict | None, request: Request) -> ReferenceSourceOut | None:
    if source is None:
        return None
    filename = source["pdf_filename"]
    pdf_url = (
        str(request.url_for("get_reference_document", filename=filename))
        if filename and document_path(filename) is not None
        else None
    )
    return ReferenceSourceOut(
        title=source["title"],
        authors=source["authors"],
        year=source["year"],
        location=source["location"],
        url=source["url"],
        pdf_url=pdf_url,
    )


@router.get("/reference-proteins", summary="Эталонные белки ФАО/ВОЗ")
async def list_reference_proteins(
    request: Request,
    catalog: Annotated[ReferenceCatalog, Depends(get_reference_catalog)],
) -> list[ReferenceProteinOut]:
    return [
        {**rp, "source": _source_out(rp["source"], request)}
        for rp in await catalog.list_reference_proteins()
    ]


@router.get("/recipes", summary="Сохранённые рецептуры (примеры)")
async def list_recipes(
    catalog: Annotated[ReferenceCatalog, Depends(get_reference_catalog)],
):
    return await catalog.list_example_recipes()


# --------------------------- расчёт ------------------------------
@router.post("/compute", summary="Рассчитать пищевую и биологическую ценность")
async def compute(
    req: CalcRequest,
    request: Request,
    calculator: Annotated[RecipeCalculator, Depends(get_calculator)],
    norms: Annotated[NormsService, Depends(get_norms_service)],
    _user: Annotated[User, Depends(get_current_user)],
):
    items = [{"product_id": it.product_id, "amount_g": it.amount_g} for it in req.items]
    result = await calculator.compute(req.reference_protein_id, items)
    # Доля от суточной нормы считается здесь же; сумма рецептуры равна 100 г,
    # поэтому макросостав — это содержание на 100 г рецептуры.
    macro = result["macro"]
    result["daily_norms"] = await norms.payload(
        pdf_url_builder(request),
        amounts_from_macros(
            macro["protein"],
            macro["fat"],
            macro["carb"],
            macro["fiber"],
            energy=result["energy_kcal"],
        ),
    )
    return result


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
