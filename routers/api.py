from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

import models
from database import get_db
from schemas import (
    SimpleCreate, ProductCreate, NutrientCreate,
    SimpleBulkCreate, ProductAutoCreate, NutrientBulkCreate
)

router = APIRouter(prefix="/api/v1")


# Вспомогательные функции
async def get_item(db: AsyncSession, model, item_id: UUID):
    item = await db.get(model, item_id)
    if not item:
        raise HTTPException(status_code=404, detail=f"{model.__name__} not found")
    return item


async def create_simple_item(db: AsyncSession, model, data):
    try:
        item = model(**data.dict())
        db.add(item)
        await db.commit()
        await db.refresh(item)
        return item
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail=f"{model.__name__} already exists")


# ==================== CATEGORIES ====================
@router.post("/categories", status_code=201, tags=["Categories"])
async def api_create_category(data: SimpleCreate, db: AsyncSession = Depends(get_db)):
    return await create_simple_item(db, models.Category, data)


@router.get("/categories", tags=["Categories"])
async def api_list_categories(name: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    query = select(models.Category)
    if name:
        query = query.where(models.Category.name.ilike(f"%{name}%"))
    res = await db.execute(query)
    return res.scalars().all()


@router.get("/categories/{id}", tags=["Categories"])
async def api_get_category(id: UUID, db: AsyncSession = Depends(get_db)):
    return await get_item(db, models.Category, id)


@router.delete("/categories/{id}", tags=["Categories"])
async def api_delete_category(id: UUID, db: AsyncSession = Depends(get_db)):
    item = await get_item(db, models.Category, id)
    try:
        await db.delete(item)
        await db.commit()
        return {"status": "deleted"}
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Cannot delete category: used in products")


@router.post("/categories/bulk", status_code=201, tags=["Categories"])
async def api_bulk_categories(data: SimpleBulkCreate, db: AsyncSession = Depends(get_db)):
    inserted = 0
    skipped = 0
    for name in data.names:
        # Проверяем наличие
        res = await db.execute(select(models.Category).where(models.Category.name == name))
        exists = res.scalar_one_or_none()

        if not exists:
            item = models.Category(name=name)
            db.add(item)
            inserted += 1
        else:
            skipped += 1

    if inserted > 0:
        await db.commit()

    return {"inserted": inserted, "skipped_duplicates": skipped}


# ==================== SUBCATEGORIES ====================
@router.post("/subcategories", status_code=201, tags=["Subcategories"])
async def api_create_subcategory(data: SimpleCreate, db: AsyncSession = Depends(get_db)):
    return await create_simple_item(db, models.Subcategory, data)


@router.get("/subcategories", tags=["Subcategories"])
async def api_list_subcategories(db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(models.Subcategory))
    return res.scalars().all()


# ==================== REGIONS ====================
@router.post("/regions", status_code=201, tags=["Regions"])
async def api_create_region(data: SimpleCreate, db: AsyncSession = Depends(get_db)):
    return await create_simple_item(db, models.Region, data)


@router.get("/regions", tags=["Regions"])
async def api_list_regions(db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(models.Region))
    return res.scalars().all()


@router.post("/regions/bulk", status_code=201, tags=["Regions"])
async def api_bulk_regions(data: SimpleBulkCreate, db: AsyncSession = Depends(get_db)):
    inserted = 0
    skipped = 0
    for name in data.names:
        res = await db.execute(select(models.Region).where(models.Region.name == name))
        exists = res.scalar_one_or_none()

        if not exists:
            item = models.Region(name=name)
            db.add(item)
            inserted += 1
        else:
            skipped += 1

    if inserted > 0:
        await db.commit()

    return {"inserted": inserted, "skipped_duplicates": skipped}


# ==================== UNITS ====================
@router.post("/units", status_code=201, tags=["Units"])
async def api_create_unit(data: SimpleCreate, db: AsyncSession = Depends(get_db)):
    return await create_simple_item(db, models.Unit, data)


@router.get("/units", tags=["Units"])
async def api_list_units(db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(models.Unit))
    return res.scalars().all()


@router.post("/units/bulk", status_code=201, tags=["Units"])
async def api_bulk_units(data: SimpleBulkCreate, db: AsyncSession = Depends(get_db)):
    inserted = 0
    skipped = 0
    for name in data.names:
        res = await db.execute(select(models.Unit).where(models.Unit.name == name))
        exists = res.scalar_one_or_none()

        if not exists:
            item = models.Unit(name=name)
            db.add(item)
            inserted += 1
        else:
            skipped += 1

    if inserted > 0:
        await db.commit()

    return {"inserted": inserted, "skipped_duplicates": skipped}


# ==================== NUTRIENT TYPES ====================
@router.post("/nutrient-types", status_code=201, tags=["Nutrient Types"])
async def api_create_nutrient_type(data: SimpleCreate, db: AsyncSession = Depends(get_db)):
    return await create_simple_item(db, models.NutrientType, data)


@router.get("/nutrient-types", tags=["Nutrient Types"])
async def api_list_nutrient_types(db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(models.NutrientType))
    return res.scalars().all()


@router.post("/nutrient-types/bulk", status_code=201, tags=["Nutrient Types"])
async def api_bulk_nutrient_types(data: SimpleBulkCreate, db: AsyncSession = Depends(get_db)):
    inserted = 0
    skipped = 0
    for name in data.names:
        res = await db.execute(select(models.NutrientType).where(models.NutrientType.name == name))
        exists = res.scalar_one_or_none()

        if not exists:
            item = models.NutrientType(name=name)
            db.add(item)
            inserted += 1
        else:
            skipped += 1

    if inserted > 0:
        await db.commit()

    return {"inserted": inserted, "skipped_duplicates": skipped}


# ==================== NUTRIENT NAMES ====================
@router.post("/nutrient-names", status_code=201, tags=["Nutrient Names"])
async def api_create_nutrient_name(data: SimpleCreate, db: AsyncSession = Depends(get_db)):
    return await create_simple_item(db, models.NutrientName, data)


@router.get("/nutrient-names", tags=["Nutrient Names"])
async def api_list_nutrient_names(db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(models.NutrientName))
    return res.scalars().all()


@router.post("/nutrient-names/bulk", status_code=201, tags=["Nutrient Names"])
async def api_bulk_nutrient_names(data: SimpleBulkCreate, db: AsyncSession = Depends(get_db)):
    inserted = 0
    skipped = 0
    for name in data.names:
        res = await db.execute(select(models.NutrientName).where(models.NutrientName.name == name))
        exists = res.scalar_one_or_none()

        if not exists:
            item = models.NutrientName(name=name)
            db.add(item)
            inserted += 1
        else:
            skipped += 1

    if inserted > 0:
        await db.commit()

    return {"inserted": inserted, "skipped_duplicates": skipped}


# ==================== PRODUCTS ====================
@router.post("/products", status_code=201, tags=["Products"])
async def api_create_product(data: ProductCreate, db: AsyncSession = Depends(get_db)):
    try:
        item = models.Product(**data.dict())
        db.add(item)
        await db.commit()
        await db.refresh(item)
        return item
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Product already exists in this region")


@router.get("/products", tags=["Products"])
async def api_list_products(db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(models.Product))
    return res.scalars().all()


@router.get("/products/{id}", tags=["Products"])
async def api_get_product(id: UUID, db: AsyncSession = Depends(get_db)):
    return await get_item(db, models.Product, id)


@router.delete("/products/{id}", tags=["Products"])
async def api_delete_product(id: UUID, db: AsyncSession = Depends(get_db)):
    item = await get_item(db, models.Product, id)
    await db.delete(item)
    await db.commit()
    return {"status": "deleted"}


@router.post("/products/bulk", status_code=201, tags=["Products"])
async def api_bulk_products(data: List[ProductCreate], db: AsyncSession = Depends(get_db)):
    # Для продуктов bulk сложнее из-за составного ключа.
    # Простая вставка:
    try:
        items = [models.Product(**p.dict()) for p in data]
        db.add_all(items)
        await db.commit()
        return {"inserted": len(items)}
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Some products already exist or invalid data")


@router.get("/products/by-region/{id}", tags=["Products"])
async def api_products_by_region(id: UUID, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(models.Product).where(models.Product.region_id == id))
    return res.scalars().all()


@router.get("/products/by-category/{id}", tags=["Products"])
async def api_products_by_category(id: UUID, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(models.Product).where(models.Product.category_id == id))
    return res.scalars().all()


@router.post("/products/auto", status_code=201, tags=["Products"])
async def api_auto_create_product(data: ProductAutoCreate, db: AsyncSession = Depends(get_db)):
    async def get_or_create(model, name):
        res = await db.execute(select(model).where(model.name == name))
        item = res.scalar_one_or_none()
        if not item:
            item = model(name=name)
            db.add(item)
            await db.flush()
        return item

    try:
        cat = await get_or_create(models.Category, data.category_name)
        reg = await get_or_create(models.Region, data.region_name)

        subcat = None
        if data.subcategory_name:
            subcat = await get_or_create(models.Subcategory, data.subcategory_name)

        product = models.Product(
            name=data.name,
            category_id=cat.id,
            region_id=reg.id,
            subcategory_id=subcat.id if subcat else None
        )
        db.add(product)
        await db.commit()
        await db.refresh(product)
        return product
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Product already exists")


@router.post("/products/auto/bulk", status_code=201, tags=["Products"])
async def api_auto_bulk_products(data: List[ProductAutoCreate], db: AsyncSession = Depends(get_db)):
    created = 0
    errors = []

    async def get_or_create(model, name):
        res = await db.execute(select(model).where(model.name == name))
        item = res.scalar_one_or_none()
        if not item:
            item = model(name=name)
            db.add(item)
            await db.flush()
        return item

    for idx, item_data in enumerate(data):
        try:
            cat = await get_or_create(models.Category, item_data.category_name)
            reg = await get_or_create(models.Region, item_data.region_name)

            subcat = None
            if item_data.subcategory_name:
                subcat = await get_or_create(models.Subcategory, item_data.subcategory_name)

            # Проверка на существование продукта (имя + регион)
            prod_res = await db.execute(
                select(models.Product).where(
                    models.Product.name == item_data.name,
                    models.Product.region_id == reg.id
                )
            )
            if prod_res.scalar_one_or_none():
                errors.append(f"Row {idx}: Product '{item_data.name}' already exists in region")
                continue

            product = models.Product(
                name=item_data.name,
                category_id=cat.id,
                region_id=reg.id,
                subcategory_id=subcat.id if subcat else None
            )
            db.add(product)
            created += 1
        except Exception as e:
            errors.append(f"Row {idx}: {str(e)}")

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        return {"warning": "Transaction rolled back due to conflict", "errors": errors}

    return {"created": created, "errors": errors}


# ==================== NUTRIENTS ====================
@router.post("/nutrients", status_code=201, tags=["Nutrients"])
async def api_create_nutrient(data: NutrientCreate, db: AsyncSession = Depends(get_db)):
    item = models.Nutrient(**data.dict())
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item


@router.get("/nutrients/product/{id}", tags=["Nutrients"])
async def api_product_nutrients(id: UUID, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(models.Nutrient).where(models.Nutrient.id_product == id))
    return res.scalars().all()


@router.post("/nutrients/bulk", status_code=201, tags=["Nutrients"])
async def api_bulk_nutrients(data: NutrientBulkCreate, db: AsyncSession = Depends(get_db)):
    try:
        items = [models.Nutrient(**n.dict()) for n in data.items]
        db.add_all(items)
        await db.commit()
        return {"inserted": len(items)}
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Duplicate nutrient entry detected")