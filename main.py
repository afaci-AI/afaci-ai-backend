from typing import Optional

from fastapi import FastAPI, Request, Depends, Form, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from uuid import UUID
import models
from database import get_db

from routers import api

app = FastAPI()

app.include_router(api.router)

templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")


# --- API для Справочников ---
@app.post("/api/categories", response_class=HTMLResponse)
async def create_category(request: Request, name: str = Form(...), db: AsyncSession = Depends(get_db)):
    try:
        new_cat = models.Category(name=name)
        db.add(new_cat)
        await db.commit()
        await db.refresh(new_cat)
        return templates.TemplateResponse(request, "partials/select_option.html", {"item": new_cat})
    except IntegrityError:
        await db.rollback()
        return templates.TemplateResponse(
            request,
            "partials/error_message.html",
            {"message": f"Категория '{name}' уже существует!"},
            status_code=400
        )


@app.post("/api/subcategories", response_class=HTMLResponse)
async def create_subcategory(request: Request, name: str = Form(...), db: AsyncSession = Depends(get_db)):
    try:
        new_item = models.Subcategory(name=name)
        db.add(new_item)
        await db.commit()
        await db.refresh(new_item)
        return templates.TemplateResponse(request, "partials/select_option.html", {"item": new_item})
    except IntegrityError:
        await db.rollback()
        return templates.TemplateResponse(request, "partials/error_message.html",
                                          {"message": f"Подкатегория '{name}' уже существует!"})


@app.post("/api/regions", response_class=HTMLResponse)
async def create_region(request: Request, name: str = Form(...), db: AsyncSession = Depends(get_db)):
    try:
        new_item = models.Region(name=name)
        db.add(new_item)
        await db.commit()
        await db.refresh(new_item)
        return templates.TemplateResponse(request, "partials/select_option.html", {"item": new_item})
    except IntegrityError:
        await db.rollback()
        return templates.TemplateResponse(request, "partials/error_message.html",
                                          {"message": f"Регион '{name}' уже существует!"})


@app.post("/api/units", response_class=HTMLResponse)
async def create_unit(request: Request, name: str = Form(...), db: AsyncSession = Depends(get_db)):
    try:
        new_item = models.Unit(name=name)
        db.add(new_item)
        await db.commit()
        await db.refresh(new_item)
        return templates.TemplateResponse(request, "partials/select_option.html", {"item": new_item})
    except IntegrityError:
        await db.rollback()
        return templates.TemplateResponse(request, "partials/error_message.html",
                                          {"message": f"Единица '{name}' уже существует!"})


@app.post("/api/nutrients_types", response_class=HTMLResponse)
async def create_nutrient_type(request: Request, name: str = Form(...), db: AsyncSession = Depends(get_db)):
    try:
        new_item = models.NutrientType(name=name)
        db.add(new_item)
        await db.commit()
        await db.refresh(new_item)
        return templates.TemplateResponse(request, "partials/select_option.html", {"item": new_item})
    except IntegrityError:
        await db.rollback()
        return templates.TemplateResponse(request, "partials/error_message.html",
                                          {"message": f"Тип '{name}' уже существует!"})


@app.post("/api/nutrients_names", response_class=HTMLResponse)
async def create_nutrient_name(request: Request, name: str = Form(...), db: AsyncSession = Depends(get_db)):
    try:
        new_item = models.NutrientName(name=name)
        db.add(new_item)
        await db.commit()
        await db.refresh(new_item)
        return templates.TemplateResponse(request, "partials/select_option.html", {"item": new_item})
    except IntegrityError:
        await db.rollback()
        return templates.TemplateResponse(request, "partials/error_message.html",
                                          {"message": f"Нутриент '{name}' уже существует!"})


# --- API для Продуктов ---
@app.post("/api/products", response_class=HTMLResponse)
async def create_product(
        request: Request,
        name: str = Form(...),
        category_id: UUID = Form(...),
        region_id: UUID = Form(...),
        subcategory_id: Optional[UUID] = Form(default=None),
        db: AsyncSession = Depends(get_db)
):
    try:
        product = models.Product(
            name=name,
            category_id=category_id,
            region_id=region_id,
            subcategory_id=subcategory_id
        )
        db.add(product)
        await db.commit()
        await db.refresh(product)

        return RedirectResponse(url=f"/products/{product.id}", status_code=303)

    except IntegrityError:
        await db.rollback()

        return HTMLResponse(
            content=f"<div style='color:red; padding:1rem;'>Ошибка: Продукт '{name}' в выбранном регионе уже существует!</div>",
            status_code=400)


# --- API для Нутриентов ---
@app.post("/api/nutrients", response_class=HTMLResponse)
async def create_nutrient(
        request: Request,
        id_product: UUID = Form(...),
        id_name_component: UUID = Form(...),
        id_type_component: UUID = Form(...),
        unit_id: UUID = Form(...),
        quantity: float = Form(...),
        db: AsyncSession = Depends(get_db)
):
    nutrient = models.Nutrient(
        id_product=id_product,
        id_name_component=id_name_component,
        id_type_component=id_type_component,
        unit_id=unit_id,
        quantity=quantity
    )
    db.add(nutrient)
    await db.commit()
    await db.refresh(nutrient)

    return templates.TemplateResponse(request, "partials/nutrient_row.html", {"item": nutrient})


# --- Страницы (Views) ---
@app.get("/", response_class=HTMLResponse)
async def index(request: Request, db: AsyncSession = Depends(get_db)):
    result_cats = await db.execute(select(models.Category))
    result_regs = await db.execute(select(models.Region))
    result_subcats = await db.execute(select(models.Subcategory))
    result_units = await db.execute(select(models.Unit))
    result_nut_names = await db.execute(select(models.NutrientName))
    result_nut_types = await db.execute(select(models.NutrientType))

    context = {
        "categories": result_cats.scalars().all(),
        "regions": result_regs.scalars().all(),
        "subcategories": result_subcats.scalars().all(),
        "units": result_units.scalars().all(),
        "nutrient_names": result_nut_names.scalars().all(),
        "nutrient_types": result_nut_types.scalars().all(),
    }

    return templates.TemplateResponse(request, "index.html", context)


@app.get("/products/{product_id}", response_class=HTMLResponse)
async def product_detail(request: Request, product_id: UUID, db: AsyncSession = Depends(get_db)):
    product = await db.get(models.Product, product_id)
    if not product:
        raise HTTPException(status_code=404)

    # Загружаем нутриенты этого продукта
    stmt = select(models.Nutrient).where(models.Nutrient.id_product == product_id)
    result = await db.execute(stmt)
    nutrients = result.scalars().all()

    # --- ВАЖНО: Загружаем ВСЕ справочники для выпадающих списков ---
    result_nut_names = await db.execute(select(models.NutrientName))
    result_nut_types = await db.execute(select(models.NutrientType))
    result_units = await db.execute(select(models.Unit))

    context = {
        "request": request,
        "product": product,
        "nutrients": nutrients,
        # Передаем списки в шаблон
        "nutrient_names": result_nut_names.scalars().all(),
        "nutrient_types": result_nut_types.scalars().all(),
        "units": result_units.scalars().all(),
    }

    return templates.TemplateResponse(request, "product_detail.html", context)