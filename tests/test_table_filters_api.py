"""Query-параметры таблиц доходят до сервиса смысловыми фильтрами."""

import unittest
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from features.table.api.deps import get_table_service
from features.table.api.router import router
from features.table.domain.filters import ExactIds, Page, Sorting, TableFilters


class RecordingService:
    def __init__(self):
        self.calls = []

    async def products(self, filters, ids, sorting, page):
        self.calls.append(("products", filters, ids, sorting, page))
        return []

    async def nutrients(self, filters, sorting, page):
        self.calls.append(("nutrients", filters, sorting, page))
        return []

    async def nutrients_csv(self, filters, sorting, page):
        self.calls.append(("csv", filters, sorting, page))
        return b""


class TableFiltersApi(unittest.TestCase):
    def setUp(self):
        self.service = RecordingService()
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_table_service] = lambda: self.service
        self.client = TestClient(app)

    def test_products_get_name_filters_ids_sorting_and_page(self):
        region_id = uuid4()
        response = self.client.get(
            "/api/v1/table/products",
            params={
                "product": "баранина",
                "category": "мясо",
                "region_id": str(region_id),
                "sort_by": "region_name",
                "sort_order": "desc",
                "limit": 5,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            self.service.calls,
            [
                (
                    "products",
                    TableFilters(category="мясо", product="баранина"),
                    ExactIds(region_id=region_id),
                    Sorting("region_name", "desc"),
                    Page(5, 0),
                )
            ],
        )

    def test_defaults_are_kept(self):
        self.client.get("/api/v1/table/nutrients", params={"nutrient_name": "Белок"})
        self.assertEqual(
            self.service.calls,
            [
                (
                    "nutrients",
                    TableFilters(nutrient_name="Белок"),
                    Sorting("product_name", "asc"),
                    Page(1000, 0),
                )
            ],
        )

    def test_csv_has_its_own_limits_and_no_subcategory(self):
        response = self.client.get(
            "/api/v1/table/nutrients/csv",
            params={"subcategory": "x", "limit": 50000},
        )
        self.assertEqual(response.status_code, 200)
        _, filters, _, page = self.service.calls[0]
        self.assertEqual(filters, TableFilters())
        self.assertEqual(page, Page(50000, 0))
        too_many = self.client.get("/api/v1/table/products", params={"limit": 50000})
        self.assertEqual(too_many.status_code, 422)


if __name__ == "__main__":
    unittest.main()
