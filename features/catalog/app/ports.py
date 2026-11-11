"""Порт хранилища справочников. Записи — непрозрачные объекты хранилища:
у них есть `id`, `name` и поля конкретного справочника."""

from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID

Row = Any


class DuplicateError(Exception):
    """Нарушена уникальность записи."""


class InUseError(Exception):
    """Запись используется другими данными и не может быть удалена."""


class CatalogRepository(Protocol):
    async def get(self, kind: str, item_id: UUID) -> Row | None: ...

    async def list(self, kind: str, name: str | None = None) -> list[Row]:
        """Все записи; `name` — фильтр «содержит» без учёта регистра."""

    async def find_by_name(self, kind: str, name: str) -> Row | None: ...

    async def add(self, kind: str, data: dict) -> Row:
        """Создаёт запись и сохраняет. DuplicateError при нарушении уникальности."""

    def stage(self, kind: str, data: dict) -> Row:
        """Добавляет запись в текущую транзакцию без сохранения."""

    async def save(self, row: Row) -> Row:
        """Сохраняет изменения. DuplicateError при нарушении уникальности."""

    async def commit(self) -> None: ...

    async def delete(self, row: Row) -> None:
        """Удаляет запись. InUseError, если на неё есть ссылки."""

    # ------------------------------------------------------ специальные
    async def default_unit_id(self, type_name: str) -> UUID | None:
        """Единица по правилу типа состава либо None."""

    async def duplicate_subcategory(
        self, category_id: UUID, name: str, exclude_id: UUID
    ) -> bool: ...

    async def duplicate_nutrient_name(
        self, type_id: UUID, name: str, exclude_id: UUID
    ) -> bool: ...

    async def has_values_in_other_unit(self, name_id: UUID, unit_id: UUID) -> bool: ...
