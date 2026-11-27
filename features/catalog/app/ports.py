"""Порты справочников.

Записи — объекты хранилища (ORM): DTO не вводятся по решению от 2026-11-09.
Протоколы ниже описывают только поля, которые читают и меняют сценарии.
Порты разделены по ответственности: записи справочников, проверки правил,
единица работы.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID


class DictionaryRow(Protocol):
    id: UUID
    name: str


class SubcategoryRow(DictionaryRow, Protocol):
    category_id: UUID


class NutrientNameRow(DictionaryRow, Protocol):
    nutrient_type_id: UUID
    unit_id: UUID
    nutrient_class: str | None


class DuplicateError(Exception):
    """Нарушена уникальность записи."""


class InUseError(Exception):
    """Запись используется другими данными и не может быть удалена."""


class DictionaryRepository(Protocol):
    """Записи любого справочника по его виду (`DictionarySpec.kind`).

    Изменения не фиксируются: это делает `UnitOfWork`. После DuplicateError или
    InUseError единица работы годится только для `rollback`.
    """

    async def get(self, kind: str, item_id: UUID) -> DictionaryRow | None: ...

    async def list(self, kind: str, name: str | None = None) -> list[DictionaryRow]:
        """Все записи; `name` — фильтр «содержит» без учёта регистра."""

    async def find_by_name(self, kind: str, name: str) -> DictionaryRow | None: ...

    async def add(self, kind: str, data: dict) -> DictionaryRow:
        """Добавляет запись. DuplicateError при нарушении уникальности."""

    async def save(self, row: DictionaryRow) -> DictionaryRow:
        """Готовит изменения записи. DuplicateError при нарушении уникальности."""

    async def delete(self, row: DictionaryRow) -> None:
        """Удаляет запись. InUseError, если на неё есть ссылки."""


class CatalogRules(Protocol):
    """Проверки, нужные только подкатегориям и названиям нутриентов."""

    async def default_unit_id(self, type_name: str) -> UUID | None:
        """Единица по правилу типа состава либо None."""

    async def duplicate_subcategory(
        self, category_id: UUID, name: str, exclude_id: UUID
    ) -> bool: ...

    async def duplicate_nutrient_name(
        self, type_id: UUID, name: str, exclude_id: UUID
    ) -> bool: ...

    async def has_values_in_other_unit(self, name_id: UUID, unit_id: UUID) -> bool: ...


class UnitOfWork(Protocol):
    """Транзакция сценария: единственное место фиксации и отката."""

    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...

    async def refresh(self, row: object) -> None:
        """Перечитывает значения, выставленные базой при фиксации."""
