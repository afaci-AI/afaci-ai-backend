"""Client payload regressions without loading local secrets or connecting to a DB."""

import importlib
import sys
import unittest
from types import ModuleType
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import ValidationError

from api.v1.schemas import (
    NutrientNameCreate,
    NutrientNameUpdate,
    NutrientUpdate,
    SubcategoryCreate,
    SubcategoryUpdate,
)


async def unused_db():
    raise AssertionError("Contract tests must not connect to a database")


# The production session module loads .env at import time. Use a dependency stub
# so these checks remain independent of developer credentials and database state.
session_stub = ModuleType("infrastructure.db.session")
session_stub.get_db = unused_db
with patch.dict(sys.modules, {"infrastructure.db.session": session_stub}):
    products = importlib.import_module("api.v1.products")


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
                result = await endpoint(
                    schema(name="Example", **{field: parent_id}), db
                )
                self.assertEqual(getattr(result, field), parent_id)
                db.get.assert_awaited_once_with(parent_model, parent_id)
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
                with self.assertRaises(HTTPException) as caught:
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
        self.audit = patch.object(products, "log_food_event").start()
        self.addCleanup(patch.stopall)

    async def test_new_name_uses_its_type_and_audits_change(self):
        new_name = products.models.NutrientName(id=uuid4(), nutrient_type_id=uuid4())
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
                with self.assertRaises(HTTPException) as caught:
                    await products.api_update_nutrient(
                        self.item.id,
                        NutrientUpdate(nutrient_name_id=name_id, quantity=3),
                        self.db,
                    )
                self.assertEqual(caught.exception.status_code, status)
                self.assertEqual(self.item.nutrient_name_id, previous_name)
                self.assertEqual(self.item.quantity, 1)
                self.db.commit.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
