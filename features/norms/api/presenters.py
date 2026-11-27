"""Представление норм и источников для HTTP: ссылки на локальные PDF."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict

from fastapi import Request

from ..app import ReferenceDocuments
from ..domain.records import NormsPayload, Source

PdfUrl = Callable[[str | None], str | None]


def pdf_url_builder(request: Request, documents: ReferenceDocuments) -> PdfUrl:
    """Ссылка на локально хранимый PDF источника или None, если файла нет."""

    def build(filename: str | None) -> str | None:
        if filename and documents.exists(filename):
            return str(request.url_for("get_reference_document", filename=filename))
        return None

    return build


def source_out(source: Source, pdf_url: PdfUrl) -> dict:
    fields = asdict(source)
    fields["pdf_url"] = pdf_url(fields.pop("pdf_filename"))
    return fields


def present_payload(payload: NormsPayload, pdf_url: PdfUrl) -> dict:
    """Ответ норм: строки как словари, источники — со ссылками на PDF.

    `norms` — прежнее имя списка `macro`: оно нужно уже выпущенным клиентам.
    """
    macro = [asdict(row) for row in payload.macro]
    return {
        "macro": macro,
        "norms": macro,
        "micro": [asdict(row) for row in payload.micro],
        "other": [asdict(row) for row in payload.other],
        "sources": [source_out(source, pdf_url) for source in payload.sources],
        "info": payload.info,
    }
