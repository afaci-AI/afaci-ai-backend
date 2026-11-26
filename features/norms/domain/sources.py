"""Реестр источников: записи `sources` и источники эталонных белков ФАО/ВОЗ."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from .records import ReferenceSource, RegistrySource, Source

# Пространство имён для стабильных идентификаторов источников эталонных белков.
_REFERENCE_SOURCE_NS = uuid.UUID("8c1d3a52-6e4f-4b7a-9d20-3f5a1c7e9b01")


@dataclass
class _SharedDocument:
    """Один документ, на который ссылаются несколько эталонов."""

    first: ReferenceSource
    names: list[str] = field(default_factory=list)

    def source(self) -> Source:
        ref = self.first
        key = (ref.title, ref.year, ref.url)
        return Source(
            id=str(uuid.uuid5(_REFERENCE_SOURCE_NS, "|".join(map(str, key)))),
            kind="article" if "Journal" in (ref.authors or "") else "document",
            title=ref.title,
            authors=ref.authors,
            year=ref.year,
            location=ref.location,
            url=ref.url,
            pdf_filename=ref.pdf_filename,
            used_for="Эталонный белок: " + ", ".join(self.names),
        )


def merge_sources(
    registry: list[RegistrySource], references: list[ReferenceSource]
) -> list[Source]:
    """Записи реестра плюс источники эталонов.

    Источники эталонов остаются в `reference_proteins` (единое место правды) и
    добавляются к реестру при чтении; совпадающие записи (один документ у
    нескольких эталонов) объединяются, в «Где применяется» перечисляются эталоны.
    """
    shared: dict[tuple, _SharedDocument] = {}
    for ref in references:
        document = shared.setdefault(
            (ref.title, ref.year, ref.url), _SharedDocument(ref)
        )
        document.names.append(ref.reference_name)
    return list(registry) + [document.source() for document in shared.values()]
