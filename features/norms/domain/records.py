"""Записи норм, состава и источников, с которыми работают правила фичи.

Хранилище и соседние фичи отдают строки-словари; в домен они попадают уже
в виде этих записей (`of`), поэтому правила опираются на поля, а не на ключи.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass


def _text_or_none(value: object) -> str | None:
    return None if value is None else str(value)


@dataclass(frozen=True)
class DailyNorm:
    """Усреднённая суточная норма нутриента (`daily_norms`)."""

    key: str
    unit: str
    value: float
    name: str = ""
    source_id: str | None = None
    basis: str | None = None
    # norm — физиологическая норма, adequate — адекватный уровень потребления.
    kind: str | None = "norm"

    @classmethod
    def of(cls, row: Mapping) -> DailyNorm:
        return cls(
            key=row["key"],
            unit=row["unit"],
            value=float(row["value"]),
            name=row.get("name") or row["key"],
            source_id=_text_or_none(row.get("source_id")),
            basis=row.get("basis"),
            kind=row.get("kind", "norm"),
        )


@dataclass(frozen=True)
class CompositionEntry:
    """Содержание нутриента на 100 г продукта или рецептуры."""

    name: str
    unit: str | None
    amount: float | None
    # Значение есть не у всех ингредиентов рецептуры: сумма неполная.
    partial: bool = False

    @classmethod
    def of(cls, row: Mapping) -> CompositionEntry:
        return cls(
            name=row["name"],
            unit=row.get("unit"),
            amount=row.get("amount"),
            partial=bool(row.get("partial", False)),
        )


@dataclass(frozen=True)
class ProductComposition:
    """Микросостав и прочие показатели продукта."""

    micro: list[CompositionEntry]
    other: list[CompositionEntry]


@dataclass(frozen=True)
class RegistrySource:
    """Запись реестра источников (`sources`)."""

    id: str
    kind: str
    title: str
    authors: str | None = None
    year: int | None = None
    location: str | None = None
    url: str | None = None
    pdf_filename: str | None = None
    used_for: str | None = None

    @classmethod
    def of(cls, row: Mapping) -> RegistrySource:
        return cls(
            id=str(row["id"]),
            kind=row["kind"],
            title=row["title"],
            authors=row.get("authors"),
            year=row.get("year"),
            location=row.get("location"),
            url=row.get("url"),
            pdf_filename=row.get("pdf_filename"),
            used_for=row.get("used_for"),
        )


@dataclass(frozen=True)
class ReferenceSource:
    """Источник эталонного белка (поля `source_*` в `reference_proteins`)."""

    reference_name: str
    title: str
    authors: str | None = None
    year: int | None = None
    location: str | None = None
    url: str | None = None
    pdf_filename: str | None = None

    @classmethod
    def of(cls, row: Mapping) -> ReferenceSource:
        return cls(
            reference_name=row["name"],
            title=row["source_title"],
            authors=row.get("source_authors"),
            year=row.get("source_year"),
            location=row.get("source_location"),
            url=row.get("source_url"),
            pdf_filename=row.get("source_pdf_filename"),
        )


# Источник для показа совпадает с записью реестра: эталоны приводятся к ней.
Source = RegistrySource
