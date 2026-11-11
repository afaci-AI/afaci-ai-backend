"""Client payload regressions without loading local secrets or connecting to a DB."""

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

from fastapi import APIRouter, FastAPI
from pydantic import ValidationError

from core.db import models
from core.errors import AppError
from features.catalog.api import router as catalog_router
from features.catalog.api.schemas import (
    NutrientNameCreate,
    NutrientNameUpdate,
    SubcategoryCreate,
    SubcategoryUpdate,
)
from features.catalog.app import CatalogService
from features.catalog.domain.rules import UNIT_MISMATCH
from features.catalog.infra.sql_repo import SqlCatalogRepository
from features.products.api import router as products_router
from features.products.api.schemas import (
    NutrientBulkCreate,
    NutrientCreate,
    NutrientUpdate,
    ProductCount,
)
from features.products.app import Caller, NutrientService, ProductService
from features.products.app.service import _unit_for
from features.products.infra.audit import FoodAuditTrail
from features.products.infra.sql_repo import SqlNutrientRepository, SqlProductRepository

NO_CALLER = Caller(None, None)


def catalog(db):
    return CatalogService(SqlCatalogRepository(db))


def nutrients(db):
    return NutrientService(SqlNutrientRepository(db), FoodAuditTrail())


async def api_create_subcategory(data, db):
    return await catalog(db).create_subcategory(data.model_dump())


async def api_create_nutrient_name(data, db):
    return await catalog(db).create_nutrient_name(data.model_dump())


async def api_update_subcategory(item_id, data, db):
    return await catalog(db).update_subcategory(
        item_id,
        name=data.name,
        category_id=data.category_id,
        provided=set(data.model_fields_set),
    )


async def api_update_nutrient_name(item_id, data, db):
    return await catalog(db).update_nutrient_name(
        item_id,
        name=data.name,
        nutrient_type_id=data.nutrient_type_id,
        unit_id=data.unit_id,
        provided=set(data.model_fields_set),
    )


async def api_count_products(db):
    service = ProductService(SqlProductRepository(db), FoodAuditTrail())
    return ProductCount(count=await service.count())


async def api_create_nutrient(data, db):
    return await nutrients(db).create(data.model_dump(), NO_CALLER)


async def api_update_nutrient(item_id, data, db):
    return await nutrients(db).update(
        item_id, data.model_dump(exclude_unset=True), NO_CALLER
    )


async def api_bulk_nutrients(data, db):
    return await nutrients(db).bulk_create(
        [n.model_dump() for n in data.items], NO_CALLER
    )


_router = APIRouter()
_router.include_router(catalog_router)
_router.include_router(products_router)

# Прежние имена обработчиков: тесты проверяют контракт, а не расположение кода.
products = SimpleNamespace(
    router=_router,
    models=models,
    UNIT_MISMATCH=UNIT_MISMATCH,
    nutrient_unit_for=_unit_for,
    api_create_subcategory=api_create_subcategory,
    api_create_nutrient_name=api_create_nutrient_name,
    api_update_subcategory=api_update_subcategory,
    api_update_nutrient_name=api_update_nutrient_name,
    api_count_products=api_count_products,
    api_create_nutrient=api_create_nutrient,
    api_update_nutrient=api_update_nutrient,
    api_bulk_nutrients=api_bulk_nutrients,
)
AUDIT_TARGET = "features.products.infra.audit.log_food_event"


class DictionaryContractChecks(unittest.IsolatedAsyncioTestCase):
    def test_registered_routes_expose_parent_fields(self):
        app = FastAPI()
        app.include_router(products.router)
        spec = app.openapi()
        for path, field in (
            ("/api/v1/subcategories", "category_id"),
            ("/api/v1/nutrient-names", "nutrient_type_id"),
        ):
            with self.subTest(path=path):
                for method, route_path in (("post", path), ("patch", path + "/{id}")):
                    body = spec["paths"][route_path][method]["requestBody"]
                    ref = body["content"]["application/json"]["schema"]["$ref"]
                    schema = spec["components"]["schemas"][ref.rsplit("/", 1)[1]]
                    self.assertIn(field, schema["properties"])
                    self.assertEqual(
                        field in schema.get("required", []), method == "post"
                    )

    async def test_create_requires_and_preserves_parent(self):
        for schema, endpoint, field, parent_model in (
            (
                SubcategoryCreate,
                products.api_create_subcategory,
                "category_id",
                products.models.Category,
            ),
            (
                NutrientNameCreate,
                products.api_create_nutrient_name,
                "nutrient_type_id",
                products.models.NutrientType,
            ),
        ):
            with self.subTest(field=field):
                with self.assertRaises(ValidationError):
                    schema(name="Example")
                parent_id = uuid4()
                db = Mock(get=AsyncMock(return_value=Mock()), commit=AsyncMock())
                db.refresh = AsyncMock()
                extra = {"unit_id": uuid4()} if field == "nutrient_type_id" else {}
                result = await endpoint(
                    schema(name="Example", **{field: parent_id}, **extra), db
                )
                self.assertEqual(getattr(result, field), parent_id)
                self.assertEqual(
                    db.get.await_args_list[0].args, (parent_model, parent_id)
                )
                db.commit.assert_awaited_once()

    async def test_patch_changes_parent_and_preserves_omitted_parent(self):
        for schema, endpoint, field in (
            (SubcategoryUpdate, products.api_update_subcategory, "category_id"),
            (
                NutrientNameUpdate,
                products.api_update_nutrient_name,
                "nutrient_type_id",
            ),
        ):
            with self.subTest(field=field):
                item = Mock(id=uuid4(), name="Before", **{field: uuid4()})
                db = Mock(get=AsyncMock(side_effect=[item, Mock()]))
                db.scalar = AsyncMock(return_value=None)
                db.commit = AsyncMock()
                db.refresh = AsyncMock()
                parent_id = uuid4()
                await endpoint(item.id, schema(**{field: parent_id}), db)
                self.assertEqual(getattr(item, field), parent_id)
                db.get.side_effect = [item, Mock()]
                await endpoint(item.id, schema(name="After"), db)
                self.assertEqual(getattr(item, field), parent_id)
                self.assertEqual(item.name, "After")

    async def test_patch_rejects_null_parent(self):
        for schema, endpoint, field in (
            (SubcategoryUpdate, products.api_update_subcategory, "category_id"),
            (
                NutrientNameUpdate,
                products.api_update_nutrient_name,
                "nutrient_type_id",
            ),
        ):
            with self.subTest(field=field):
                db = Mock(get=AsyncMock(return_value=Mock()), commit=AsyncMock())
                with self.assertRaises(AppError) as caught:
                    await endpoint(uuid4(), schema(**{field: None}), db)
                self.assertEqual(caught.exception.status_code, 422)
                db.commit.assert_not_awaited()


class ProductCountChecks(unittest.IsolatedAsyncioTestCase):
    async def test_returns_total_and_zero_for_empty_database(self):
        for total, expected in ((115, 115), (0, 0), (None, 0)):
            with self.subTest(total=total):
                db = Mock(scalar=AsyncMock(return_value=total))
                result = await products.api_count_products(db)
                self.assertEqual(result.count, expected)

    def test_route_is_public_parameterless_and_not_shadowed_by_item_route(self):
        app = FastAPI()
        app.include_router(products.router)
        operation = app.openapi()["paths"]["/api/v1/products/count"]["get"]
        self.assertNotIn("parameters", operation)
        self.assertNotIn("security", operation)
        paths = [route.path for route in app.routes]
        self.assertLess(
            paths.index("/api/v1/products/count"), paths.index("/api/v1/products/{id}")
        )


class NutrientUpdateChecks(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.old_type = uuid4()
        self.item = products.models.Nutrient(
            id=uuid4(),
            product_id=uuid4(),
            nutrient_name_id=uuid4(),
            nutrient_type_id=self.old_type,
            unit_id=uuid4(),
            quantity=1,
        )
        self.db = Mock(get=AsyncMock(), commit=AsyncMock(), refresh=AsyncMock())
        self.audit = patch(AUDIT_TARGET).start()
        self.addCleanup(patch.stopall)

    async def test_new_name_uses_its_type_and_audits_change(self):
        new_name = products.models.NutrientName(
            id=uuid4(), nutrient_type_id=uuid4(), unit_id=self.item.unit_id
        )
        self.db.get.side_effect = [self.item, new_name]
        await products.api_update_nutrient(
            self.item.id, NutrientUpdate(nutrient_name_id=new_name.id), self.db
        )
        self.assertEqual(self.item.nutrient_name_id, new_name.id)
        self.assertEqual(self.item.nutrient_type_id, new_name.nutrient_type_id)
        changes = self.audit.call_args.kwargs["changes"]
        self.assertEqual(
            changes["new"]["nutrient_type_id"], str(new_name.nutrient_type_id)
        )

    async def test_quantity_only_preserves_name_and_type(self):
        self.db.get.return_value = self.item
        await products.api_update_nutrient(
            self.item.id, NutrientUpdate(quantity=2), self.db
        )
        self.assertEqual(self.item.nutrient_type_id, self.old_type)
        self.assertEqual(self.item.quantity, 2)
        self.db.get.assert_awaited_once()

    async def test_missing_or_null_name_does_not_mutate_or_commit(self):
        for name_id, status in ((uuid4(), 404), (None, 422)):
            with self.subTest(name_id=name_id):
                self.db.get.side_effect = [self.item, None]
                previous_name = self.item.nutrient_name_id
                with self.assertRaises(AppError) as caught:
                    await products.api_update_nutrient(
                        self.item.id,
                        NutrientUpdate(nutrient_name_id=name_id, quantity=3),
                        self.db,
                    )
                self.assertEqual(caught.exception.status_code, status)
                self.assertEqual(self.item.nutrient_name_id, previous_name)
                self.assertEqual(self.item.quantity, 1)
                self.db.commit.assert_not_awaited()


def make_name(unit_id=None, type_name=None):
    return products.models.NutrientName(
        id=uuid4(), nutrient_type_id=uuid4(), name="Test", unit_id=unit_id
    )


class FixedUnitChecks(unittest.IsolatedAsyncioTestCase):
    """Единица нутриента назначается сервером по названию и не принимает чужую."""

    def setUp(self):
        self.audit = patch(AUDIT_TARGET).start()
        self.addCleanup(patch.stopall)
        self.unit = uuid4()
        self.other_unit = uuid4()

    def db_with(self, *rows):
        return Mock(
            get=AsyncMock(side_effect=list(rows)),
            add=Mock(),
            commit=AsyncMock(),
            refresh=AsyncMock(),
        )

    def test_name_unit_is_used_when_client_omits_it(self):
        name = make_name(self.unit)
        self.assertEqual(products.nutrient_unit_for(name, None), self.unit)
        self.assertEqual(products.nutrient_unit_for(name, self.unit), self.unit)

    def test_other_unit_is_rejected(self):
        with self.assertRaises(AppError) as caught:
            products.nutrient_unit_for(make_name(self.unit), self.other_unit)
        self.assertEqual(caught.exception.status_code, 400)
        self.assertEqual(caught.exception.detail, products.UNIT_MISMATCH)

    def test_name_without_fixed_unit_still_needs_explicit_unit(self):
        name = make_name(None)
        self.assertEqual(products.nutrient_unit_for(name, self.unit), self.unit)
        with self.assertRaises(AppError) as caught:
            products.nutrient_unit_for(name, None)
        self.assertEqual(caught.exception.status_code, 422)

    def test_unit_is_optional_in_create_schema(self):
        payload = {"product_id": uuid4(), "nutrient_name_id": uuid4(), "quantity": 1}
        self.assertIsNone(NutrientCreate(**payload).unit_id)

    async def test_create_assigns_unit_from_name(self):
        name = make_name(self.unit)
        db = self.db_with(name)
        data = NutrientCreate(product_id=uuid4(), nutrient_name_id=name.id, quantity=2)
        result = await products.api_create_nutrient(data, db)
        self.assertEqual(result.unit_id, self.unit)
        self.assertEqual(result.nutrient_type_id, name.nutrient_type_id)

    async def test_create_rejects_incompatible_unit_without_saving(self):
        name = make_name(self.unit)
        db = self.db_with(name)
        data = NutrientCreate(
            product_id=uuid4(),
            nutrient_name_id=name.id,
            unit_id=self.other_unit,
            quantity=2,
        )
        with self.assertRaises(AppError) as caught:
            await products.api_create_nutrient(data, db)
        self.assertEqual(caught.exception.status_code, 400)
        db.commit.assert_not_awaited()

    async def test_update_switching_name_takes_new_name_unit(self):
        old_unit, new_unit = uuid4(), uuid4()
        item = products.models.Nutrient(
            id=uuid4(),
            product_id=uuid4(),
            nutrient_name_id=uuid4(),
            nutrient_type_id=uuid4(),
            unit_id=old_unit,
            quantity=1,
        )
        new_name = make_name(new_unit)
        db = self.db_with(item, new_name)
        await products.api_update_nutrient(
            item.id, NutrientUpdate(nutrient_name_id=new_name.id), db
        )
        self.assertEqual(item.unit_id, new_unit)

    async def test_update_rejects_unit_of_another_name(self):
        item = products.models.Nutrient(
            id=uuid4(),
            product_id=uuid4(),
            nutrient_name_id=uuid4(),
            nutrient_type_id=uuid4(),
            unit_id=self.unit,
            quantity=1,
        )
        new_name = make_name(self.unit)
        db = self.db_with(item, new_name)
        with self.assertRaises(AppError) as caught:
            await products.api_update_nutrient(
                item.id,
                NutrientUpdate(nutrient_name_id=new_name.id, unit_id=self.other_unit),
                db,
            )
        self.assertEqual(caught.exception.status_code, 400)
        self.assertEqual(item.unit_id, self.unit)
        db.commit.assert_not_awaited()

    async def test_update_quantity_only_keeps_unit_and_skips_lookup(self):
        item = products.models.Nutrient(
            id=uuid4(),
            product_id=uuid4(),
            nutrient_name_id=uuid4(),
            nutrient_type_id=uuid4(),
            unit_id=self.unit,
            quantity=1,
        )
        db = self.db_with(item)
        await products.api_update_nutrient(item.id, NutrientUpdate(quantity=5), db)
        self.assertEqual(item.unit_id, self.unit)
        self.assertEqual(db.get.await_count, 1)

    async def test_bulk_assigns_units_and_rejects_mismatch(self):
        name = make_name(self.unit)
        db = Mock(
            scalars=AsyncMock(return_value=[name]),
            add_all=Mock(),
            commit=AsyncMock(),
            refresh=AsyncMock(),
            rollback=AsyncMock(),
        )
        good = NutrientBulkCreate(
            items=[
                NutrientCreate(product_id=uuid4(), nutrient_name_id=name.id, quantity=1)
            ]
        )
        self.assertEqual((await products.api_bulk_nutrients(good, db))["inserted"], 1)
        added = db.add_all.call_args.args[0][0]
        self.assertEqual(added.unit_id, self.unit)
        bad = NutrientBulkCreate(
            items=[
                NutrientCreate(
                    product_id=uuid4(),
                    nutrient_name_id=name.id,
                    unit_id=self.other_unit,
                    quantity=1,
                )
            ]
        )
        with self.assertRaises(AppError) as caught:
            await products.api_bulk_nutrients(bad, db)
        self.assertEqual(caught.exception.status_code, 400)


class NutrientNameUnitChecks(unittest.IsolatedAsyncioTestCase):
    """Единица нового названия — по правилу типа; менять её с несовместимыми значениями нельзя."""

    def type_with(self, name):
        return products.models.NutrientType(id=uuid4(), name=name)

    async def test_create_uses_unit_of_the_type_rule(self):
        for type_name, unit_name in (
            ("Химический состав", "%/100г"),
            ("Аминокислотный состав", "мг/100г"),
            ("Минеральный состав", "мг/100г"),
        ):
            with self.subTest(type=type_name):
                unit_id = uuid4()
                nutrient_type = self.type_with(type_name)
                db = Mock(
                    get=AsyncMock(return_value=nutrient_type),
                    scalar=AsyncMock(return_value=unit_id),
                    commit=AsyncMock(),
                    refresh=AsyncMock(),
                    add=Mock(),
                )
                result = await products.api_create_nutrient_name(
                    NutrientNameCreate(name="X", nutrient_type_id=nutrient_type.id), db
                )
                self.assertEqual(result.unit_id, unit_id)

    async def test_create_for_type_without_rule_requires_unit(self):
        nutrient_type = self.type_with("Пользовательский тип")
        db = Mock(
            get=AsyncMock(return_value=nutrient_type),
            scalar=AsyncMock(return_value=None),
            commit=AsyncMock(),
        )
        with self.assertRaises(AppError) as caught:
            await products.api_create_nutrient_name(
                NutrientNameCreate(name="X", nutrient_type_id=nutrient_type.id), db
            )
        self.assertEqual(caught.exception.status_code, 422)
        db.commit.assert_not_awaited()

    async def test_create_with_explicit_unit_checks_it_exists(self):
        db = Mock(
            get=AsyncMock(side_effect=[Mock(), None]),
            commit=AsyncMock(),
        )
        with self.assertRaises(AppError) as caught:
            await products.api_create_nutrient_name(
                NutrientNameCreate(name="X", nutrient_type_id=uuid4(), unit_id=uuid4()),
                db,
            )
        self.assertEqual(caught.exception.status_code, 404)

    async def test_unit_change_is_blocked_when_values_use_another_unit(self):
        item = make_name(uuid4())
        db = Mock(
            get=AsyncMock(side_effect=[item, Mock(), Mock()]),
            scalar=AsyncMock(side_effect=[None, uuid4()]),
            commit=AsyncMock(),
            refresh=AsyncMock(),
        )
        with self.assertRaises(AppError) as caught:
            await products.api_update_nutrient_name(
                item.id, NutrientNameUpdate(unit_id=uuid4()), db
            )
        self.assertEqual(caught.exception.status_code, 400)
        db.commit.assert_not_awaited()

    async def test_unit_can_be_set_when_no_value_conflicts(self):
        item = make_name(None)
        new_unit = uuid4()
        db = Mock(
            get=AsyncMock(side_effect=[item, Mock(), Mock()]),
            scalar=AsyncMock(side_effect=[None, None]),
            commit=AsyncMock(),
            refresh=AsyncMock(),
        )
        await products.api_update_nutrient_name(
            item.id, NutrientNameUpdate(unit_id=new_unit), db
        )
        self.assertEqual(item.unit_id, new_unit)

    async def test_null_unit_is_rejected(self):
        item = make_name(uuid4())
        db = Mock(
            get=AsyncMock(side_effect=[item, Mock()]),
            scalar=AsyncMock(return_value=None),
            commit=AsyncMock(),
        )
        with self.assertRaises(AppError) as caught:
            await products.api_update_nutrient_name(
                item.id, NutrientNameUpdate(unit_id=None), db
            )
        self.assertEqual(caught.exception.status_code, 422)


if __name__ == "__main__":
    unittest.main()
