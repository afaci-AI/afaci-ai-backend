"""Порты продуктов и нутриентов. Записи — непрозрачные объекты хранилища."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID

Row = Any


class DuplicateError(Exception):
    """Нарушена уникальность записи."""


@dataclass
class Caller:
    """Кто выполняет запрос: пользователь (если определён) и заголовок авторизации."""

    user: Any | None
    authorization: str | None


class AuditTrail(Protocol):
    """Бизнес-аудит продуктов; сбой записи не должен ломать операцию."""

    def snapshot_product(self, row: Row) -> dict: ...

    def snapshot_nutrient(self, row: Row) -> dict: ...

    def diff(self, old: dict, new: dict) -> tuple[dict, dict]: ...

    def log(
        self, event: str, caller: Caller, target_id: str | UUID, changes: dict
    ) -> None: ...


class ProductRepository(Protocol):
    async def get(self, product_id: UUID) -> Row | None: ...

    async def list(self) -> list[Row]: ...

    async def count(self) -> int: ...

    async def by_region(self, region_id: UUID) -> list[Row]: ...

    async def by_category(self, category_id: UUID) -> list[Row]: ...

    async def add(self, data: dict) -> Row:
        """Создаёт продукт и сохраняет. DuplicateError при нарушении уникальности."""

    async def add_many(self, items: list[dict]) -> list[Row]:
        """Создаёт продукты одной транзакцией. DuplicateError при нарушении."""

    async def update(self, row: Row, patch: dict) -> Row:
        """Применяет поля и сохраняет. DuplicateError при нарушении уникальности."""

    async def delete(self, row: Row) -> None: ...

    # ------------------------------------------------ автосоздание продуктов
    async def get_or_create_named(self, kind: str, name: str) -> Row:
        """Категория, регион или подкатегория по имени (создаётся и сбрасывается в БД)."""

    async def find_in_region(self, name: str, region_id: UUID) -> Row | None: ...

    async def stage(self, data: dict) -> Row:
        """Добавляет продукт в транзакцию и сбрасывает в БД без фиксации."""

    async def commit(self) -> None:
        """Фиксирует транзакцию. DuplicateError при нарушении уникальности."""

    async def rollback(self) -> None: ...

    async def refresh(self, row: Row) -> None: ...


class NutrientRepository(Protocol):
    async def get(self, nutrient_id: UUID) -> Row | None: ...

    async def list(self) -> list[Row]: ...

    async def by_product(self, product_id: UUID) -> list[Row]: ...

    async def get_name(self, name_id: UUID) -> Row | None:
        """Название нутриента (с типом и единицей)."""

    async def names_by_ids(self, ids: set[UUID]) -> dict[UUID, Row]: ...

    async def add(self, data: dict) -> Row: ...

    async def add_many(self, items: list[dict]) -> list[Row]:
        """Одной транзакцией. DuplicateError при нарушении уникальности."""

    async def update(self, row: Row, patch: dict) -> Row: ...

    async def delete(self, row: Row) -> None: ...
