from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from api.v1.schemas import (
    NutrientBulkCreate,
    NutrientCreate,
    NutrientUpdate,
    ProductAutoCreate,
    ProductCreate,
    ProductUpdate,
    SimpleBulkCreate,
    SimpleCreate,
    SimpleUpdate,
)
from infrastructure.audit.food_audit import (
    FOOD_ENTITY,
    compute_diff,
    log_food_event,
    resolve_food_user,
    snapshot_nutrient,
    snapshot_product,
)
from infrastructure.auth import get_current_user_optional
from infrastructure.db import models
from infrastructure.db.models import User
from infrastructure.db.session import get_db

router = APIRouter(prefix="/api/v1")

CurrentUserOpt = Annotated[User | None, Depends(get_current_user_optional)]


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
async def api_create_category(
    data: SimpleCreate, db: Annotated[AsyncSession, Depends(get_db)]
):
    return await create_simple_item(db, models.Category, data)


@router.get("/categories", tags=["Categories"])
async def api_list_categories(
    db: Annotated[AsyncSession, Depends(get_db)], name: str | None = None
):
    query = select(models.Category)
    if name:
        query = query.where(models.Category.name.ilike(f"%{name}%"))
    res = await db.execute(query)
    return res.scalars().all()


@router.get("/categories/{id}", tags=["Categories"])
async def api_get_category(id: UUID, db: Annotated[AsyncSession, Depends(get_db)]):
    return await get_item(db, models.Category, id)


@router.delete("/categories/{id}", tags=["Categories"])
async def api_delete_category(id: UUID, db: Annotated[AsyncSession, Depends(get_db)]):
    item = await get_item(db, models.Category, id)
    try:
        await db.delete(item)
        await db.commit()
        return {"status": "deleted"}
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=400, detail="Cannot delete category: used in products"
        )


@router.patch("/categories/{id}", tags=["Categories"])
async def api_update_category(
    id: UUID, data: SimpleUpdate, db: Annotated[AsyncSession, Depends(get_db)]
):
    item = await get_item(db, models.Category, id)
    if data.name is not None and data.name != item.name:
        res = await db.execute(
            select(models.Category).where(models.Category.name == data.name)
        )
        if res.scalar_one_or_none():
            raise HTTPException(
                status_code=400, detail="Category with this name already exists"
            )
        item.name = data.name
    await db.commit()
    await db.refresh(item)
    return item


@router.post("/categories/bulk", status_code=201, tags=["Categories"])
async def api_bulk_categories(
    data: SimpleBulkCreate, db: Annotated[AsyncSession, Depends(get_db)]
):
    inserted = 0
    skipped = 0
    for name in data.names:
        res = await db.execute(
            select(models.Category).where(models.Category.name == name)
        )
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
async def api_create_subcategory(
    data: SimpleCreate, db: Annotated[AsyncSession, Depends(get_db)]
):
    return await create_simple_item(db, models.Subcategory, data)


@router.get("/subcategories", tags=["Subcategories"])
async def api_list_subcategories(db: Annotated[AsyncSession, Depends(get_db)]):
    res = await db.execute(select(models.Subcategory))
    return res.scalars().all()


@router.get("/subcategories/{id}", tags=["Subcategories"])
async def api_get_subcategory(id: UUID, db: Annotated[AsyncSession, Depends(get_db)]):
    return await get_item(db, models.Subcategory, id)


@router.delete("/subcategories/{id}", tags=["Subcategories"])
async def api_delete_subcategory(
    id: UUID, db: Annotated[AsyncSession, Depends(get_db)]
):
    item = await get_item(db, models.Subcategory, id)
    try:
        await db.delete(item)
        await db.commit()
        return {"status": "deleted"}
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=400, detail="Cannot delete subcategory: used in products"
        )


@router.patch("/subcategories/{id}", tags=["Subcategories"])
async def api_update_subcategory(
    id: UUID, data: SimpleUpdate, db: Annotated[AsyncSession, Depends(get_db)]
):
    item = await get_item(db, models.Subcategory, id)
    if data.name is not None and data.name != item.name:
        res = await db.execute(
            select(models.Subcategory).where(
                models.Subcategory.category_id == item.category_id,
                models.Subcategory.name == data.name,
            )
        )
        if res.scalar_one_or_none():
            raise HTTPException(
                status_code=400,
                detail="Subcategory with this name already exists in this category",
            )
        item.name = data.name
    await db.commit()
    await db.refresh(item)
    return item


# ==================== REGIONS ====================
@router.post("/regions", status_code=201, tags=["Regions"])
async def api_create_region(
    data: SimpleCreate, db: Annotated[AsyncSession, Depends(get_db)]
):
    return await create_simple_item(db, models.Region, data)


@router.get("/regions", tags=["Regions"])
async def api_list_regions(db: Annotated[AsyncSession, Depends(get_db)]):
    res = await db.execute(select(models.Region))
    return res.scalars().all()


@router.get("/regions/{id}", tags=["Regions"])
async def api_get_region(id: UUID, db: Annotated[AsyncSession, Depends(get_db)]):
    return await get_item(db, models.Region, id)


@router.delete("/regions/{id}", tags=["Regions"])
async def api_delete_region(id: UUID, db: Annotated[AsyncSession, Depends(get_db)]):
    item = await get_item(db, models.Region, id)
    try:
        await db.delete(item)
        await db.commit()
        return {"status": "deleted"}
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=400, detail="Cannot delete region: used in products"
        )


@router.patch("/regions/{id}", tags=["Regions"])
async def api_update_region(
    id: UUID, data: SimpleUpdate, db: Annotated[AsyncSession, Depends(get_db)]
):
    item = await get_item(db, models.Region, id)
    if data.name is not None and data.name != item.name:
        res = await db.execute(
            select(models.Region).where(models.Region.name == data.name)
        )
        if res.scalar_one_or_none():
            raise HTTPException(
                status_code=400, detail="Region with this name already exists"
            )
        item.name = data.name
    await db.commit()
    await db.refresh(item)
    return item


@router.post("/regions/bulk", status_code=201, tags=["Regions"])
async def api_bulk_regions(
    data: SimpleBulkCreate, db: Annotated[AsyncSession, Depends(get_db)]
):
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
async def api_create_unit(
    data: SimpleCreate, db: Annotated[AsyncSession, Depends(get_db)]
):
    return await create_simple_item(db, models.Unit, data)


@router.get("/units", tags=["Units"])
async def api_list_units(db: Annotated[AsyncSession, Depends(get_db)]):
    res = await db.execute(select(models.Unit))
    return res.scalars().all()


@router.get("/units/{id}", tags=["Units"])
async def api_get_unit(id: UUID, db: Annotated[AsyncSession, Depends(get_db)]):
    return await get_item(db, models.Unit, id)


@router.delete("/units/{id}", tags=["Units"])
async def api_delete_unit(id: UUID, db: Annotated[AsyncSession, Depends(get_db)]):
    item = await get_item(db, models.Unit, id)
    try:
        await db.delete(item)
        await db.commit()
        return {"status": "deleted"}
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=400, detail="Cannot delete unit: used in nutrients"
        )


@router.patch("/units/{id}", tags=["Units"])
async def api_update_unit(
    id: UUID, data: SimpleUpdate, db: Annotated[AsyncSession, Depends(get_db)]
):
    item = await get_item(db, models.Unit, id)
    if data.name is not None and data.name != item.name:
        res = await db.execute(select(models.Unit).where(models.Unit.name == data.name))
        if res.scalar_one_or_none():
            raise HTTPException(
                status_code=400, detail="Unit with this name already exists"
            )
        item.name = data.name
    await db.commit()
    await db.refresh(item)
    return item


@router.post("/units/bulk", status_code=201, tags=["Units"])
async def api_bulk_units(
    data: SimpleBulkCreate, db: Annotated[AsyncSession, Depends(get_db)]
):
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
async def api_create_nutrient_type(
    data: SimpleCreate, db: Annotated[AsyncSession, Depends(get_db)]
):
    return await create_simple_item(db, models.NutrientType, data)


@router.get("/nutrient-types", tags=["Nutrient Types"])
async def api_list_nutrient_types(db: Annotated[AsyncSession, Depends(get_db)]):
    res = await db.execute(select(models.NutrientType))
    return res.scalars().all()


@router.get("/nutrient-types/{id}", tags=["Nutrient Types"])
async def api_get_nutrient_type(id: UUID, db: Annotated[AsyncSession, Depends(get_db)]):
    return await get_item(db, models.NutrientType, id)


@router.delete("/nutrient-types/{id}", tags=["Nutrient Types"])
async def api_delete_nutrient_type(
    id: UUID, db: Annotated[AsyncSession, Depends(get_db)]
):
    item = await get_item(db, models.NutrientType, id)
    try:
        await db.delete(item)
        await db.commit()
        return {"status": "deleted"}
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=400,
            detail="Cannot delete nutrient type: used in nutrient names",
        )


@router.patch("/nutrient-types/{id}", tags=["Nutrient Types"])
async def api_update_nutrient_type(
    id: UUID, data: SimpleUpdate, db: Annotated[AsyncSession, Depends(get_db)]
):
    item = await get_item(db, models.NutrientType, id)
    if data.name is not None and data.name != item.name:
        res = await db.execute(
            select(models.NutrientType).where(models.NutrientType.name == data.name)
        )
        if res.scalar_one_or_none():
            raise HTTPException(
                status_code=400, detail="Nutrient type with this name already exists"
            )
        item.name = data.name
    await db.commit()
    await db.refresh(item)
    return item


@router.post("/nutrient-types/bulk", status_code=201, tags=["Nutrient Types"])
async def api_bulk_nutrient_types(
    data: SimpleBulkCreate, db: Annotated[AsyncSession, Depends(get_db)]
):
    inserted = 0
    skipped = 0
    for name in data.names:
        res = await db.execute(
            select(models.NutrientType).where(models.NutrientType.name == name)
        )
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
async def api_create_nutrient_name(
    data: SimpleCreate, db: Annotated[AsyncSession, Depends(get_db)]
):
    return await create_simple_item(db, models.NutrientName, data)


@router.get("/nutrient-names", tags=["Nutrient Names"])
async def api_list_nutrient_names(db: Annotated[AsyncSession, Depends(get_db)]):
    res = await db.execute(select(models.NutrientName))
    return res.scalars().all()


@router.get("/nutrient-names/{id}", tags=["Nutrient Names"])
async def api_get_nutrient_name(id: UUID, db: Annotated[AsyncSession, Depends(get_db)]):
    return await get_item(db, models.NutrientName, id)


@router.delete("/nutrient-names/{id}", tags=["Nutrient Names"])
async def api_delete_nutrient_name(
    id: UUID, db: Annotated[AsyncSession, Depends(get_db)]
):
    item = await get_item(db, models.NutrientName, id)
    try:
        await db.delete(item)
        await db.commit()
        return {"status": "deleted"}
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=400, detail="Cannot delete nutrient name: used in nutrients"
        )


@router.patch("/nutrient-names/{id}", tags=["Nutrient Names"])
async def api_update_nutrient_name(
    id: UUID, data: SimpleUpdate, db: Annotated[AsyncSession, Depends(get_db)]
):
    item = await get_item(db, models.NutrientName, id)
    if data.name is not None and data.name != item.name:
        res = await db.execute(
            select(models.NutrientName).where(models.NutrientName.name == data.name)
        )
        if res.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Nutrient name already exists")
        item.name = data.name
    await db.commit()
    await db.refresh(item)
    return item


@router.post("/nutrient-names/bulk", status_code=201, tags=["Nutrient Names"])
async def api_bulk_nutrient_names(
    data: SimpleBulkCreate, db: Annotated[AsyncSession, Depends(get_db)]
):
    inserted = 0
    skipped = 0
    for name in data.names:
        res = await db.execute(
            select(models.NutrientName).where(models.NutrientName.name == name)
        )
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
async def api_create_product(
    data: ProductCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    authorization: Annotated[str | None, Header()] = None,
    current_user: CurrentUserOpt = None,
):
    try:
        payload = data.model_dump() if hasattr(data, "model_dump") else data.dict()
        item = models.Product(**payload)
        db.add(item)
        await db.commit()
        await db.refresh(item)
        log_food_event(
            event="FOOD_PRODUCT_CREATED",
            user=resolve_food_user(current_user, authorization),
            target_entity=FOOD_ENTITY,
            target_id=item.id,
            changes={"old": None, "new": snapshot_product(item)},
        )
        return item
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=400, detail="Product already exists in this region"
        )


@router.get("/products", tags=["Products"])
async def api_list_products(db: Annotated[AsyncSession, Depends(get_db)]):
    res = await db.execute(select(models.Product))
    return res.scalars().all()


@router.get("/products/{id}", tags=["Products"])
async def api_get_product(id: UUID, db: Annotated[AsyncSession, Depends(get_db)]):
    return await get_item(db, models.Product, id)


@router.delete("/products/{id}", tags=["Products"])
async def api_delete_product(
    id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    authorization: Annotated[str | None, Header()] = None,
    current_user: CurrentUserOpt = None,
):
    item = await get_item(db, models.Product, id)
    old_snapshot = snapshot_product(item)
    await db.delete(item)
    await db.commit()
    log_food_event(
        event="FOOD_PRODUCT_DELETED",
        user=resolve_food_user(current_user, authorization),
        target_entity=FOOD_ENTITY,
        target_id=id,
        changes={"old": old_snapshot, "new": None},
    )
    return {"status": "deleted"}


@router.patch("/products/{id}", tags=["Products"])
async def api_update_product(
    id: UUID,
    data: ProductUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    authorization: Annotated[str | None, Header()] = None,
    current_user: CurrentUserOpt = None,
):
    item = await get_item(db, models.Product, id)
    old_snapshot = snapshot_product(item)
    patch = (
        data.model_dump(exclude_unset=True)
        if hasattr(data, "model_dump")
        else data.dict(exclude_unset=True)
    )
    if not patch:
        return item
    for field, value in patch.items():
        setattr(item, field, value)
    try:
        await db.commit()
        await db.refresh(item)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=400, detail="Product already exists in this region"
        )
    new_snapshot = snapshot_product(item)
    old_diff, new_diff = compute_diff(old_snapshot, new_snapshot)
    if old_diff:
        log_food_event(
            event="FOOD_PRODUCT_UPDATED",
            user=resolve_food_user(current_user, authorization),
            target_entity=FOOD_ENTITY,
            target_id=id,
            changes={"old": old_diff, "new": new_diff},
        )
    return item


@router.post("/products/bulk", status_code=201, tags=["Products"])
async def api_bulk_products(
    data: list[ProductCreate],
    db: Annotated[AsyncSession, Depends(get_db)],
    authorization: Annotated[str | None, Header()] = None,
    current_user: CurrentUserOpt = None,
):
    try:
        payloads = [
            p.model_dump() if hasattr(p, "model_dump") else p.dict() for p in data
        ]
        items = [models.Product(**p) for p in payloads]
        db.add_all(items)
        await db.commit()
        for it in items:
            await db.refresh(it)
        target_ids = [str(it.id) for it in items]
        # Одна запись на bulk — защита диска при сотнях позиций
        log_food_event(
            event="FOOD_PRODUCT_BULK_CREATED",
            user=resolve_food_user(current_user, authorization),
            target_entity=FOOD_ENTITY,
            target_id=target_ids[0] if target_ids else "bulk",
            changes={
                "old": None,
                "new": {
                    "count": len(items),
                    "target_ids": target_ids[:100],
                    "truncated": len(target_ids) > 100,
                },
            },
        )
        return {"inserted": len(items)}
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=400, detail="Some products already exist or invalid data"
        )


@router.get("/products/by-region/{id}", tags=["Products"])
async def api_products_by_region(
    id: UUID, db: Annotated[AsyncSession, Depends(get_db)]
):
    res = await db.execute(select(models.Product).where(models.Product.region_id == id))
    return res.scalars().all()


@router.get("/products/by-category/{id}", tags=["Products"])
async def api_products_by_category(
    id: UUID, db: Annotated[AsyncSession, Depends(get_db)]
):
    res = await db.execute(
        select(models.Product).where(models.Product.category_id == id)
    )
    return res.scalars().all()


@router.post("/products/auto", status_code=201, tags=["Products"])
async def api_auto_create_product(
    data: ProductAutoCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    authorization: Annotated[str | None, Header()] = None,
    current_user: CurrentUserOpt = None,
):
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
            subcategory_id=subcat.id if subcat else None,
        )
        db.add(product)
        await db.commit()
        await db.refresh(product)
        log_food_event(
            event="FOOD_PRODUCT_CREATED",
            user=resolve_food_user(current_user, authorization),
            target_entity=FOOD_ENTITY,
            target_id=product.id,
            changes={"old": None, "new": snapshot_product(product)},
        )
        return product
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Product already exists")


@router.post("/products/auto/bulk", status_code=201, tags=["Products"])
async def api_auto_bulk_products(
    data: list[ProductAutoCreate],
    db: Annotated[AsyncSession, Depends(get_db)],
    authorization: Annotated[str | None, Header()] = None,
    current_user: CurrentUserOpt = None,
):
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

    created_products: list[models.Product] = []
    for idx, item_data in enumerate(data):
        try:
            cat = await get_or_create(models.Category, item_data.category_name)
            reg = await get_or_create(models.Region, item_data.region_name)
            subcat = None
            if item_data.subcategory_name:
                subcat = await get_or_create(
                    models.Subcategory, item_data.subcategory_name
                )
            prod_res = await db.execute(
                select(models.Product).where(
                    models.Product.name == item_data.name,
                    models.Product.region_id == reg.id,
                )
            )
            if prod_res.scalar_one_or_none():
                errors.append(
                    f"Row {idx}: Product '{item_data.name}' already exists in region"
                )
                continue
            product = models.Product(
                name=item_data.name,
                category_id=cat.id,
                region_id=reg.id,
                subcategory_id=subcat.id if subcat else None,
            )
            db.add(product)
            await db.flush()
            created_products.append(product)
            created += 1
        except Exception as e:  # noqa: BLE001
            errors.append(f"Row {idx}: {e!s}")

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        return {"warning": "Transaction rolled back due to conflict", "errors": errors}

    if created > 0:
        target_ids = [str(p.id) for p in created_products]
        log_food_event(
            event="FOOD_PRODUCT_BULK_CREATED",
            user=resolve_food_user(current_user, authorization),
            target_entity=FOOD_ENTITY,
            target_id="bulk",
            changes={
                "old": None,
                "new": {
                    "count": created,
                    "target_ids": target_ids[:100],
                    "truncated": len(target_ids) > 100,
                },
            },
        )

    return {"created": created, "errors": errors}


# ==================== NUTRIENTS ====================
@router.post("/nutrients", status_code=201, tags=["Nutrients"])
async def api_create_nutrient(
    data: NutrientCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    authorization: Annotated[str | None, Header()] = None,
    current_user: CurrentUserOpt = None,
):
    payload = data.model_dump() if hasattr(data, "model_dump") else data.dict()
    item = models.Nutrient(**payload)
    db.add(item)
    await db.commit()
    await db.refresh(item)
    log_food_event(
        event="FOOD_PRODUCT_CREATED",
        user=resolve_food_user(current_user, authorization),
        target_entity=FOOD_ENTITY,
        target_id=item.product_id,
        changes={
            "old": None,
            "new": snapshot_nutrient(item),
            "nutrient_id": str(item.id),
        },
    )
    return item


@router.get("/nutrients", tags=["Nutrients"])
async def api_list_nutrients(db: Annotated[AsyncSession, Depends(get_db)]):
    res = await db.execute(select(models.Nutrient))
    return res.scalars().all()


@router.get("/nutrients/{id}", tags=["Nutrients"])
async def api_get_nutrient(id: UUID, db: Annotated[AsyncSession, Depends(get_db)]):
    return await get_item(db, models.Nutrient, id)


@router.delete("/nutrients/{id}", tags=["Nutrients"])
async def api_delete_nutrient(
    id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    authorization: Annotated[str | None, Header()] = None,
    current_user: CurrentUserOpt = None,
):
    item = await get_item(db, models.Nutrient, id)
    old_snapshot = snapshot_nutrient(item)
    product_id = item.product_id
    await db.delete(item)
    await db.commit()
    log_food_event(
        event="FOOD_PRODUCT_DELETED",
        user=resolve_food_user(current_user, authorization),
        target_entity=FOOD_ENTITY,
        target_id=product_id,
        changes={
            "old": old_snapshot,
            "new": None,
            "nutrient_id": str(id),
        },
    )
    return {"status": "deleted"}


@router.patch("/nutrients/{id}", tags=["Nutrients"])
async def api_update_nutrient(
    id: UUID,
    data: NutrientUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    authorization: Annotated[str | None, Header()] = None,
    current_user: CurrentUserOpt = None,
):
    item = await get_item(db, models.Nutrient, id)
    old_snapshot = snapshot_nutrient(item)
    patch = (
        data.model_dump(exclude_unset=True)
        if hasattr(data, "model_dump")
        else data.dict(exclude_unset=True)
    )
    if not patch:
        return item
    for field, value in patch.items():
        setattr(item, field, value)
    await db.commit()
    await db.refresh(item)
    new_snapshot = snapshot_nutrient(item)
    old_diff, new_diff = compute_diff(old_snapshot, new_snapshot)
    if old_diff:
        log_food_event(
            event="FOOD_PRODUCT_UPDATED",
            user=resolve_food_user(current_user, authorization),
            target_entity=FOOD_ENTITY,
            target_id=item.product_id,
            changes={
                "old": old_diff,
                "new": new_diff,
                "nutrient_id": str(id),
            },
        )
    return item


@router.get("/nutrients/product/{id}", tags=["Nutrients"])
async def api_product_nutrients(id: UUID, db: Annotated[AsyncSession, Depends(get_db)]):
    res = await db.execute(
        select(models.Nutrient).where(models.Nutrient.product_id == id)
    )
    return res.scalars().all()


@router.post("/nutrients/bulk", status_code=201, tags=["Nutrients"])
async def api_bulk_nutrients(
    data: NutrientBulkCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    authorization: Annotated[str | None, Header()] = None,
    current_user: CurrentUserOpt = None,
):
    try:
        payloads = [
            n.model_dump() if hasattr(n, "model_dump") else n.dict() for n in data.items
        ]
        items = [models.Nutrient(**n) for n in payloads]
        db.add_all(items)
        await db.commit()
        for it in items:
            await db.refresh(it)
        nutrient_ids = [str(it.id) for it in items]
        product_ids = list({str(it.product_id) for it in items})
        log_food_event(
            event="FOOD_PRODUCT_BULK_CREATED",
            user=resolve_food_user(current_user, authorization),
            target_entity=FOOD_ENTITY,
            target_id=product_ids[0] if product_ids else "bulk",
            changes={
                "old": None,
                "new": {
                    "count": len(items),
                    "target_ids": nutrient_ids[:100],
                    "product_ids": product_ids[:20],
                    "truncated": len(nutrient_ids) > 100,
                },
            },
        )
        return {"inserted": len(items)}
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Duplicate nutrient entry detected")
