"""Сценарии продуктов и нутриентов: транзакцию фиксирует только единица работы."""

import unittest
from types import SimpleNamespace
from uuid import uuid4

from core.errors import BadRequestError
from features.products.app import (
    Caller,
    DuplicateError,
    NutrientService,
    ProductService,
)

CALLER = Caller(actor="user:42")


class FakeUnitOfWork:
    def __init__(self):
        self.calls = []

    async def commit(self):
        self.calls.append("commit")

    async def rollback(self):
        self.calls.append("rollback")

    async def refresh(self, row):
        self.calls.append("refresh")


class FakeAudit:
    def __init__(self):
        self.logged = []

    def snapshot_product(self, row):
        return {"name": row.name}

    def snapshot_nutrient(self, row):
        return {"quantity": row.quantity}

    def diff(self, old, new):
        changed = {k for k in new if old.get(k) != new[k]}
        return {k: old.get(k) for k in changed}, {k: new[k] for k in changed}

    def log(self, event, caller, target_id, changes):
        self.logged.append((event, caller.actor))


class FakeProducts:
    """Хранилище без фиксации: только готовит изменения или сообщает о дубле."""

    def __init__(self, duplicate=False):
        self.duplicate = duplicate
        self.row = SimpleNamespace(id=uuid4(), name="Говядина")

    async def get(self, product_id):
        return self.row

    async def add(self, data):
        if self.duplicate:
            raise DuplicateError("unique")
        return SimpleNamespace(id=uuid4(), **data)

    async def update(self, row, patch):
        if self.duplicate:
            raise DuplicateError("unique")
        for key, value in patch.items():
            setattr(row, key, value)
        return row

    async def delete(self, row):
        pass


class ProductTransactions(unittest.IsolatedAsyncioTestCase):
    def build(self, **repo):
        self.uow, self.audit = FakeUnitOfWork(), FakeAudit()
        return ProductService(FakeProducts(**repo), self.uow, self.audit)

    async def test_create_commits_then_audits_with_callers_actor(self):
        service = self.build()
        await service.create({"name": "Баранина"}, CALLER)
        self.assertEqual(self.uow.calls, ["commit", "refresh"])
        self.assertEqual(self.audit.logged, [("FOOD_PRODUCT_CREATED", "user:42")])

    async def test_duplicate_on_create_rolls_back_without_audit(self):
        service = self.build(duplicate=True)
        with self.assertRaises(BadRequestError):
            await service.create({"name": "Говядина"}, CALLER)
        self.assertEqual(self.uow.calls, ["rollback"])
        self.assertEqual(self.audit.logged, [])

    async def test_duplicate_on_update_rolls_back(self):
        service = self.build(duplicate=True)
        with self.assertRaises(BadRequestError):
            await service.update(uuid4(), {"name": "Баранина"}, CALLER)
        self.assertEqual(self.uow.calls, ["rollback"])

    async def test_empty_patch_touches_nothing(self):
        service = self.build()
        await service.update(uuid4(), {}, CALLER)
        self.assertEqual(self.uow.calls, [])
        self.assertEqual(self.audit.logged, [])

    async def test_delete_commits_and_audits(self):
        service = self.build()
        await service.delete(uuid4(), CALLER)
        self.assertEqual(self.uow.calls, ["commit"])
        self.assertEqual(self.audit.logged, [("FOOD_PRODUCT_DELETED", "user:42")])


class FakeNutrients:
    def __init__(self, duplicate=False):
        self.duplicate = duplicate
        self.name = SimpleNamespace(
            id=uuid4(), nutrient_type_id=uuid4(), unit_id=uuid4()
        )

    async def get_name(self, name_id):
        return self.name

    async def add(self, data):
        if self.duplicate:
            raise DuplicateError("unique")
        return SimpleNamespace(id=uuid4(), **data)


class NutrientTransactions(unittest.IsolatedAsyncioTestCase):
    def build(self, **repo):
        self.uow, self.audit = FakeUnitOfWork(), FakeAudit()
        return NutrientService(FakeNutrients(**repo), self.uow, self.audit)

    def payload(self):
        return {"product_id": uuid4(), "nutrient_name_id": uuid4(), "quantity": 1}

    async def test_create_commits_and_takes_unit_from_name(self):
        service = self.build()
        item = await service.create(self.payload(), CALLER)
        self.assertEqual(self.uow.calls, ["commit", "refresh"])
        self.assertIsNotNone(item.unit_id)

    async def test_duplicate_nutrient_is_400_and_rolled_back(self):
        service = self.build(duplicate=True)
        with self.assertRaises(BadRequestError):
            await service.create(self.payload(), CALLER)
        self.assertEqual(self.uow.calls, ["rollback"])
        self.assertEqual(self.audit.logged, [])


if __name__ == "__main__":
    unittest.main()
