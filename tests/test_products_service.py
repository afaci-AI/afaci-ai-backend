"""Сценарии продуктов и нутриентов: транзакцию фиксирует только единица работы."""

import unittest
from types import SimpleNamespace
from uuid import uuid4

from core.errors import BadRequestError
from features.products.app import (
    Caller,
    DuplicateError,
    NewNutrient,
    NewProduct,
    NutrientChanges,
    NutrientService,
    ProductChanges,
    ProductService,
)

CALLER = Caller(actor="user:42")


def new_product(name):
    return NewProduct(name=name, category_id=uuid4(), region_id=uuid4())


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

    def log(self, event, caller, target_id, changes):
        self.logged.append((event, caller.actor))


class FakeProductSnapshots:
    def of(self, row):
        return {"name": row.name}


class FakeNutrientSnapshots:
    def of(self, row):
        return {"quantity": row.quantity}


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
        return ProductService(
            FakeProducts(**repo), self.uow, self.audit, FakeProductSnapshots()
        )

    async def test_create_commits_then_audits_with_callers_actor(self):
        service = self.build()
        await service.create(new_product("Баранина"), CALLER)
        self.assertEqual(self.uow.calls, ["commit", "refresh"])
        self.assertEqual(self.audit.logged, [("FOOD_PRODUCT_CREATED", "user:42")])

    async def test_duplicate_on_create_rolls_back_without_audit(self):
        service = self.build(duplicate=True)
        with self.assertRaises(BadRequestError):
            await service.create(new_product("Говядина"), CALLER)
        self.assertEqual(self.uow.calls, ["rollback"])
        self.assertEqual(self.audit.logged, [])

    async def test_duplicate_on_update_rolls_back(self):
        service = self.build(duplicate=True)
        with self.assertRaises(BadRequestError):
            await service.update(
                uuid4(),
                ProductChanges("Баранина", provided=frozenset({"name"})),
                CALLER,
            )
        self.assertEqual(self.uow.calls, ["rollback"])

    async def test_empty_patch_touches_nothing(self):
        service = self.build()
        await service.update(uuid4(), ProductChanges(), CALLER)
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

    async def get(self, nutrient_id):
        return SimpleNamespace(id=nutrient_id, product_id=uuid4(), quantity=1)

    async def get_name(self, name_id):
        return self.name

    async def add(self, data):
        if self.duplicate:
            raise DuplicateError("unique")
        return SimpleNamespace(id=uuid4(), **data)


class NutrientTransactions(unittest.IsolatedAsyncioTestCase):
    def build(self, **repo):
        self.uow, self.audit = FakeUnitOfWork(), FakeAudit()
        return NutrientService(
            FakeNutrients(**repo), self.uow, self.audit, FakeNutrientSnapshots()
        )

    def payload(self):
        return NewNutrient(product_id=uuid4(), nutrient_name_id=uuid4(), quantity=1)

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

    async def test_create_does_not_change_the_command(self):
        command = self.payload()
        await self.build().create(command, CALLER)
        self.assertIsNone(command.unit_id)

    async def test_empty_changes_touch_nothing(self):
        service = self.build()
        await service.update(uuid4(), NutrientChanges(), CALLER)
        self.assertEqual(self.uow.calls, [])


if __name__ == "__main__":
    unittest.main()
