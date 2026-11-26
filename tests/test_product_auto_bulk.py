"""Автосоздание продуктов пачкой: ожидаемые и неожиданные сбои разделены."""

import unittest
from types import SimpleNamespace
from uuid import uuid4

from features.products.app import Caller, DuplicateError, ProductImportService
from features.products.app.product_import import BULK_CONFLICT

CALLER = Caller(actor="Anonymous")


class FakeNames:
    def __init__(self):
        self.rows = {}

    async def _named(self, kind, name):
        return self.rows.setdefault((kind, name), SimpleNamespace(id=uuid4()))

    async def category(self, name):
        return await self._named("category", name)

    async def region(self, name):
        return await self._named("region", name)

    async def subcategory(self, name):
        return await self._named("subcategory", name)


class FakeProducts:
    def __init__(self, fail_on=None):
        self.staged = []
        self.fail_on = fail_on or {}

    async def find_in_region(self, name, region_id):
        return next(
            (p for p in self.staged if p.name == name and p.region_id == region_id),
            None,
        )

    async def add(self, data):
        error = self.fail_on.get(data["name"])
        if error is not None:
            raise error
        row = SimpleNamespace(id=uuid4(), **data)
        self.staged.append(row)
        return row


class FakeUnitOfWork:
    def __init__(self):
        self.calls = []

    async def commit(self):
        self.calls.append("commit")

    async def rollback(self):
        self.calls.append("rollback")

    async def refresh(self, row):
        pass


class FakeAudit:
    def __init__(self):
        self.events = []

    def log(self, event, caller, target_id, changes):
        self.events.append(event)


def row(name, region="Кыргызстан"):
    return {"name": name, "category_name": "Мясо", "region_name": region}


class AutoBulk(unittest.IsolatedAsyncioTestCase):
    def build(self, products):
        self.uow, self.audit = FakeUnitOfWork(), FakeAudit()
        return ProductImportService(products, FakeNames(), self.uow, self.audit)

    async def test_existing_product_is_skipped_and_rest_committed(self):
        service = self.build(FakeProducts())
        result = await service.auto_bulk(
            [row("Говядина"), row("Говядина"), row("Баранина")], CALLER
        )
        self.assertEqual(result["created"], 2)
        self.assertEqual(len(result["errors"]), 1)
        self.assertIn("Row 1", result["errors"][0])
        self.assertEqual(self.uow.calls, ["commit"])
        self.assertEqual(self.audit.events, ["FOOD_PRODUCT_BULK_CREATED"])

    async def test_unique_conflict_rolls_back_whole_batch(self):
        products = FakeProducts(fail_on={"Баранина": DuplicateError("unique")})
        service = self.build(products)
        result = await service.auto_bulk([row("Говядина"), row("Баранина")], CALLER)
        self.assertEqual(result["warning"], BULK_CONFLICT)
        self.assertIn("Row 1", result["errors"][0])
        self.assertEqual(self.uow.calls, ["rollback"])
        self.assertEqual(self.audit.events, [])

    async def test_unexpected_failure_is_not_turned_into_row_error(self):
        products = FakeProducts(fail_on={"Баранина": RuntimeError("db down")})
        service = self.build(products)
        with self.assertRaises(RuntimeError):
            await service.auto_bulk([row("Говядина"), row("Баранина")], CALLER)
        self.assertEqual(self.uow.calls, ["rollback"])
        self.assertEqual(self.audit.events, [])


if __name__ == "__main__":
    unittest.main()
