"""Входные данные расчёта: продукт с нутриентами и эталонный белок.

Формулы работают со словарями; ключи этих словарей задаются только здесь,
в `report_item` и `formula_input`, а не в хранилище и не в сервисе.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class ProductNutrients:
    """Продукт и его нутриенты на 100 г, по типам состава."""

    product_id: str
    name: str
    region: str | None
    subcategory: str | None
    chem: dict[str, float] = field(default_factory=dict)
    amino: dict[str, float] = field(default_factory=dict)
    micro: dict[str, float] = field(default_factory=dict)
    other: dict[str, float] = field(default_factory=dict)
    units: dict[str, str | None] = field(default_factory=dict)

    def report_item(self, amount_g: float) -> dict:
        """Ингредиент в формате `compute_report`."""
        return {
            "product_id": self.product_id,
            "name": self.name,
            "region": self.region,
            "subcategory": self.subcategory,
            "chem": self.chem,
            "amino": self.amino,
            "micro": self.micro,
            "other": self.other,
            "units": self.units,
            "amount_g": amount_g,
        }


@dataclass(frozen=True, slots=True)
class ReferenceSource:
    title: str
    authors: str | None = None
    year: int | None = None
    location: str | None = None
    url: str | None = None


@dataclass(frozen=True, slots=True)
class ReferenceProtein:
    """Эталонный белок: значения НАК по группам аминокислот."""

    id: str
    name: str
    year: int | None
    description: str | None
    source: ReferenceSource | None
    values: dict[str, float]

    def formula_input(self) -> dict:
        """Эталон в формате `compute_report` и оптимизаторов."""
        source = self.source
        return {
            "id": self.id,
            "name": self.name,
            "year": self.year,
            "description": self.description,
            "source": (
                {
                    "title": source.title,
                    "authors": source.authors,
                    "year": source.year,
                    "location": source.location,
                    "url": source.url,
                }
                if source is not None
                else None
            ),
            "values": dict(self.values),
        }
