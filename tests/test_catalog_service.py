"""Сценарии справочников: вид — описание справочника, фиксирует только единица работы."""

import unittest
from types import SimpleNamespace
from uuid import uuid4

from core.errors import BadRequestError, NotFoundError, UnprocessableError
from features.catalog.app import (
    CatalogService,
    DuplicateError,
    InUseError,
    NewNutrientName,
    NewSubcategory,
    SubcategoryChanges,
)
from features.catalog.domain.dictionaries import CATEGORIES, REGIONS, SUBCATEGORIES
from features.catalog.domain.nutrient_units import AMINO_ACID_TYPE


class FakeUnitOfWork:
    def __init__(self):
        self.calls = []

    async def commit(self):
        self.calls.append("commit")

    async def rollback(self):
        self.calls.append("rollback")

    async def refresh(self, row):
        self.calls.append("refresh")


class FakeDictionaries:
    """Хранилище без фиксации: готовит изменения или сообщает о нарушении."""

    def __init__(self, *, rows=(), duplicate=False, in_use=False):
        self.rows = {row.id: row for row in rows}
        self.duplicate = duplicate
        self.in_use = in_use
        self.added = []

    async def get(self, kind, item_id):
        return self.rows.get(item_id)

    async def list(self, kind, name=None):
        return list(self.rows.values())

    async def find_by_name(self, kind, name):
        return next((r for r in self.rows.values() if r.name == name), None)

    async def add(self, kind, data):
        if self.duplicate:
            raise DuplicateError("unique")
        row = SimpleNamespace(id=uuid4(), **data)
        self.added.append((kind, row))
        return row

    async def save(self, row):
        if self.duplicate:
            raise DuplicateError("unique")
        return row

    async def delete(self, row):
        if self.in_use:
            raise InUseError("fk")


class NoRules:
    def __init__(self, default_unit=None):
        self.default_unit = default_unit

    async def default_unit_id(self, type_name):
        return self.default_unit

    async def duplicate_subcategory(self, category_id, name, exclude_id):
        return False


def row(name="Мясо", **fields):
    return SimpleNamespace(id=uuid4(), name=name, **fields)


class CatalogTransactions(unittest.IsolatedAsyncioTestCase):
    def build(self, *, default_unit=None, **repo):
        self.uow = FakeUnitOfWork()
        self.repo = FakeDictionaries(**repo)
        return CatalogService(self.repo, NoRules(default_unit), self.uow)

    async def test_create_commits_then_refreshes(self):
        await self.build().create(REGIONS, "Сибирь")
        self.assertEqual(self.uow.calls, ["commit", "refresh"])
        self.assertEqual(self.repo.added[0][0], "region")

    async def test_duplicate_rolls_back_with_message_of_the_dictionary(self):
        service = self.build(duplicate=True)
        with self.assertRaises(BadRequestError) as caught:
            await service.create(REGIONS, "Сибирь")
        self.assertEqual(caught.exception.detail, "Region already exists")
        self.assertEqual(self.uow.calls, ["rollback"])

    async def test_missing_item_uses_not_found_message_of_the_dictionary(self):
        with self.assertRaises(NotFoundError) as caught:
            await self.build().get(SUBCATEGORIES, uuid4())
        self.assertEqual(caught.exception.detail, "Subcategory not found")

    async def test_delete_in_use_rolls_back(self):
        item = row()
        service = self.build(rows=[item], in_use=True)
        with self.assertRaises(BadRequestError) as caught:
            await service.delete(CATEGORIES, item.id)
        self.assertEqual(caught.exception.detail, CATEGORIES.in_use_message)
        self.assertEqual(self.uow.calls, ["rollback"])

    async def test_bulk_adds_new_names_in_one_transaction(self):
        service = self.build(rows=[row("Мясо")])
        result = await service.bulk(CATEGORIES, ["Мясо", "Рыба", "Птица"])
        self.assertEqual(result, {"inserted": 2, "skipped_duplicates": 1})
        self.assertEqual(self.uow.calls, ["commit"])

    async def test_bulk_duplicate_is_400_and_rolls_back_whole_batch(self):
        service = self.build(duplicate=True)
        with self.assertRaises(BadRequestError):
            await service.bulk(CATEGORIES, ["Рыба"])
        self.assertEqual(self.uow.calls, ["rollback"])

    async def test_subcategory_checks_parent_category(self):
        service = self.build()
        with self.assertRaises(NotFoundError) as caught:
            await service.create_subcategory(NewSubcategory("Говядина", uuid4()))
        self.assertEqual(caught.exception.detail, "Category not found")
        self.assertEqual(self.uow.calls, [])

    async def test_subcategory_rename_duplicate_rolls_back(self):
        category = row("Мясо")
        item = row("Говядина", category_id=category.id)
        service = self.build(rows=[category, item], duplicate=True)
        with self.assertRaises(BadRequestError) as caught:
            await service.update_subcategory(
                item.id,
                SubcategoryChanges(name="Телятина", provided=frozenset({"name"})),
            )
        self.assertEqual(
            caught.exception.detail, "Subcategory already exists in this category"
        )
        self.assertEqual(self.uow.calls, ["rollback"])

    async def test_nutrient_name_gets_default_unit_and_class_from_type(self):
        nutrient_type = row(AMINO_ACID_TYPE)
        unit_id = uuid4()
        service = self.build(rows=[nutrient_type], default_unit=unit_id)
        command = NewNutrientName("Лизин", nutrient_type.id)
        await service.create_nutrient_name(command)
        saved = self.repo.added[0][1]
        self.assertEqual((saved.unit_id, saved.nutrient_class), (unit_id, "amino"))
        self.assertIsNone(command.unit_id)

    async def test_nutrient_name_without_any_unit_is_422(self):
        nutrient_type = row(AMINO_ACID_TYPE)
        service = self.build(rows=[nutrient_type])
        with self.assertRaises(UnprocessableError):
            await service.create_nutrient_name(
                NewNutrientName("Лизин", nutrient_type.id)
            )
        self.assertEqual(self.uow.calls, [])


if __name__ == "__main__":
    unittest.main()
