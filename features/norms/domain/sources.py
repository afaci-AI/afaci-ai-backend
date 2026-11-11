"""Реестр источников: записи `sources` и источники эталонных белков ФАО/ВОЗ."""

from __future__ import annotations

import uuid
from collections.abc import Callable, Mapping

PdfUrl = Callable[[str | None], str | None]

# Пространство имён для стабильных идентификаторов источников эталонных белков.
_REFERENCE_SOURCE_NS = uuid.UUID("8c1d3a52-6e4f-4b7a-9d20-3f5a1c7e9b01")


def registry_source(row: Mapping, pdf_url: PdfUrl) -> dict:
    return {
        "id": str(row["id"]),
        "kind": row["kind"],
        "title": row["title"],
        "authors": row["authors"],
        "year": row["year"],
        "location": row["location"],
        "url": row["url"],
        "pdf_url": pdf_url(row["pdf_filename"]),
        "used_for": row["used_for"],
    }


def merge_sources(
    registry: list[Mapping], references: list[Mapping], pdf_url: PdfUrl
) -> list[dict]:
    """Записи реестра плюс источники эталонов.

    Источники эталонов остаются в `reference_proteins` (единое место правды) и
    добавляются к реестру при чтении; совпадающие записи (один документ у
    нескольких эталонов) объединяются, в «Где применяется» перечисляются эталоны.
    """
    result = [registry_source(row, pdf_url) for row in registry]
    merged: dict[tuple, dict] = {}
    for ref in references:
        key = (ref["source_title"], ref["source_year"], ref["source_url"])
        entry = merged.get(key)
        if entry is None:
            authors = ref["source_authors"] or ""
            entry = {
                "id": str(uuid.uuid5(_REFERENCE_SOURCE_NS, "|".join(map(str, key)))),
                "kind": "article" if "Journal" in authors else "document",
                "title": ref["source_title"],
                "authors": ref["source_authors"],
                "year": ref["source_year"],
                "location": ref["source_location"],
                "url": ref["source_url"],
                "pdf_url": pdf_url(ref["source_pdf_filename"]),
                "used_for": None,
                "_names": [],
            }
            merged[key] = entry
        entry["_names"].append(ref["name"])
    for entry in merged.values():
        names = entry.pop("_names")
        entry["used_for"] = "Эталонный белок: " + ", ".join(names)
        result.append(entry)
    return result
