"""PDF-документы источников: есть ли файл и где он лежит."""

from __future__ import annotations

from pathlib import Path

from core.errors import NotFoundError

from .ports import DocumentStorage

DOCUMENT_NOT_FOUND = "Документ не найден"


class ReferenceDocuments:
    def __init__(self, storage: DocumentStorage) -> None:
        self._storage = storage

    def exists(self, filename: str | None) -> bool:
        return bool(filename) and self._storage.path(filename) is not None

    def find(self, filename: str) -> Path:
        path = self._storage.path(filename)
        if path is None:
            raise NotFoundError(DOCUMENT_NOT_FOUND)
        return path
