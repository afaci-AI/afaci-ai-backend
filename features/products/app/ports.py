"""Порты продуктов и нутриентов.

Записи продуктов и справочников — объекты хранилища (ORM): DTO для этой фичи
не вводятся по решению от 2026-11-09, сущности есть только у рецептур.
Протоколы записей описывают только поля, которые читают сценарии. Порты
разделены по ответственности: хранилище, справочники, единица работы.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID


class ReferenceRow(Protocol):
    """Запись справочника (категория, регион, подкатегория)."""

    id: UUID


class ProductRow(Protocol):
    id: UUID


class NutrientNameRow(Protocol):
    id: UUID
    nutrient_type_id: UUID
    unit_id: UUID | None


class NutrientRow(Protocol):
    id: UUID
    product_id: UUID
    nutrient_name_id: UUID


class Actor(Protocol):
    """Пользователь, от имени которого выполняется запрос."""

    id: UUID


class DuplicateError(Exception):
    """Нарушена уникальность записи."""


@dataclass
class Caller:
    """Кто выполняет запрос: пользователь (если определён) и заголовок авторизации."""

    user: Actor | None
    authorization: str | None


class AuditTrail(Protocol):
    """Бизнес-аудит продуктов; сбой записи не должен ломать операцию."""

    def snapshot_product(self, row: ProductRow) -> dict: ...

    def snapshot_nutrient(self, row: NutrientRow) -> dict: ...

    def diff(self, old: dict, new: dict) -> tuple[dict, dict]: ...

    def log(
        self, event: str, caller: Caller, target_id: str | UUID, changes: dict
    ) -> None: ...


class ProductRepository(Protocol):
    async def get(self, product_id: UUID) -> ProductRow | None: ...

    async def list(self) -> list[ProductRow]: ...

    async def count(self) -> int: ...

    async def by_region(self, region_id: UUID) -> list[ProductRow]: ...

    async def by_category(self, category_id: UUID) -> list[ProductRow]: ...

    async def find_in_region(self, name: str, region_id: UUID) -> ProductRow | None: ...

    async def add(self, data: dict) -> ProductRow:
        """Создаёт продукт и сохраняет. DuplicateError при нарушении уникальности."""

    async def add_many(self, items: list[dict]) -> list[ProductRow]:
        """Создаёт продукты одной транзакцией. DuplicateError при нарушении."""

    async def update(self, row: ProductRow, patch: dict) -> ProductRow:
        """Применяет поля и сохраняет. DuplicateError при нарушении уникальности."""

    async def delete(self, row: ProductRow) -> None: ...

    async def stage(self, data: dict) -> ProductRow:
        """Добавляет продукт в текущую единицу работы без фиксации.

        DuplicateError при нарушении уникальности; единица работы после этого
        годится только для `rollback`.
        """


class ReferenceNames(Protocol):
    """Справочники по имени: найти или добавить в текущую единицу работы."""

    async def category(self, name: str) -> ReferenceRow: ...

    async def region(self, name: str) -> ReferenceRow: ...

    async def subcategory(self, name: str) -> ReferenceRow: ...


class UnitOfWork(Protocol):
    """Транзакция, общая для операций `stage` и справочников."""

    async def commit(self) -> None:
        """Фиксирует транзакцию. DuplicateError при нарушении уникальности."""

    async def rollback(self) -> None: ...

    async def refresh(self, row: object) -> None: ...


class NutrientRepository(Protocol):
    async def get(self, nutrient_id: UUID) -> NutrientRow | None: ...

    async def list(self) -> list[NutrientRow]: ...

    async def by_product(self, product_id: UUID) -> list[NutrientRow]: ...

    async def get_name(self, name_id: UUID) -> NutrientNameRow | None:
        """Название нутриента (с типом и единицей)."""

    async def names_by_ids(self, ids: set[UUID]) -> dict[UUID, NutrientNameRow]: ...

    async def add(self, data: dict) -> NutrientRow: ...

    async def add_many(self, items: list[dict]) -> list[NutrientRow]:
        """Одной транзакцией. DuplicateError при нарушении уникальности."""

    async def update(self, row: NutrientRow, patch: dict) -> NutrientRow: ...

    async def delete(self, row: NutrientRow) -> None: ...
