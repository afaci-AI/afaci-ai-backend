"""Access policy regressions without local secrets or a database connection."""

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

from fastapi import APIRouter, FastAPI
from fastapi.responses import Response
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

import core.security as authentication
from api.v1 import auth, users
from core.db import models
from core.db.session import get_db
from features.catalog.api import router as catalog_router
from features.products.api import router as products_router

_catalog = APIRouter()
_catalog.include_router(catalog_router)
_catalog.include_router(products_router)
products = SimpleNamespace(router=_catalog, models=models)


class AccessPolicyChecks(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.app = FastAPI()
        for router in (products.router, auth.router, users.router):
            self.app.include_router(router)
        self.db = Mock(execute=AsyncMock(), commit=AsyncMock(), delete=AsyncMock())
        self.app.dependency_overrides[get_db] = lambda: self.db
        self.client = TestClient(self.app)
        self.addCleanup(self.client.close)

    def test_removed_routes_return_404_without_database_writes(self):
        for method, path in (
            ("POST", "/api/v1/auth/register"),
            ("DELETE", f"/api/v1/users/{uuid4()}/permanent"),
        ):
            with self.subTest(path=path):
                self.assertEqual(
                    self.client.request(method, path, json={}).status_code, 404
                )
        self.db.execute.assert_not_awaited()
        self.db.delete.assert_not_awaited()
        self.db.commit.assert_not_awaited()

    def test_every_catalog_mutation_rejects_anonymous_and_viewer(self):
        routes = [
            route
            for route in products.router.routes
            if isinstance(route, APIRoute)
            and route.methods & {"POST", "PATCH", "PUT", "DELETE"}
        ]
        self.assertTrue(routes)
        for role, status in ((None, 401), ("viewer", 403)):
            if role:
                self.app.dependency_overrides[authentication.get_current_user] = (
                    lambda: Mock(role="viewer")
                )
            for route in routes:
                path = route.path.replace("{id}", str(uuid4()))
                method = next(iter(route.methods))
                with self.subTest(role=role, method=method, path=path):
                    response = self.client.request(method, path, json={})
                    self.assertEqual(response.status_code, status)
        self.db.execute.assert_not_awaited()
        self.db.commit.assert_not_awaited()

    def test_every_catalog_mutation_accepts_admin_and_editor_at_guard(self):
        catalog_paths = {route.path for route in products.router.routes}
        for route in self.app.routes:
            if not isinstance(route, APIRoute) or route.path not in catalog_paths:
                continue
            if not route.methods & {"POST", "PATCH", "PUT", "DELETE"}:
                continue
            # Preserve actual authorization dependencies, replace only DB-writing
            # handler. Invalid bodies can return 422 after authorization succeeds.
            handler = AsyncMock(return_value=Response(status_code=204))
            route.dependant.call = handler
            for role in ("admin", "editor"):
                self.app.dependency_overrides[authentication.get_current_user] = (
                    lambda role=role: Mock(role=role)
                )
                path = route.path.replace("{id}", str(uuid4()))
                with self.subTest(role=role, path=path):
                    response = self.client.request(
                        next(iter(route.methods)), path, json={}
                    )
                    self.assertIn(response.status_code, (204, 422))
        self.db.execute.assert_not_awaited()
        self.db.commit.assert_not_awaited()

    def test_user_creation_requires_admin(self):
        path = "/api/v1/users"
        self.assertEqual(self.client.post(path, json={}).status_code, 401)
        for role in ("viewer", "editor"):
            self.app.dependency_overrides[authentication.get_current_user] = (
                lambda role=role: Mock(role=role)
            )
            self.assertEqual(self.client.post(path, json={}).status_code, 403)
        self.db.commit.assert_not_awaited()

    async def test_deactivation_preserves_recipes_groups_and_ingredients(self):
        recipe = products.models.SavedRecipe(id=uuid4())
        ingredient = products.models.SavedRecipeItem(id=uuid4())
        recipe.items = [ingredient]
        group = products.models.RecipeGroup(id=uuid4())
        user = products.models.User(
            id=uuid4(), is_active=True, groups=[group], saved_recipes=[recipe]
        )
        self.db.get = AsyncMock(return_value=user)
        result = await users.deactivate_user(user.id, self.db, Mock(id=uuid4()))
        self.assertEqual(result, {"status": "deactivated"})
        self.assertFalse(user.is_active)
        self.assertEqual(user.groups, [group])
        self.assertEqual(user.saved_recipes, [recipe])
        self.assertEqual(recipe.items, [ingredient])
        self.db.delete.assert_not_awaited()
        self.db.commit.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
