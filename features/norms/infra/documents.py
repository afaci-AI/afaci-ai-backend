"""Локальное хранилище PDF-документов источников."""

from __future__ import annotations

import os
import re
from pathlib import Path

_PDF_FILENAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\.pdf", re.IGNORECASE)
_DEFAULT_ROOT = "uploads/reference-documents"


class LocalDocumentStorage:
    """Отдаёт только плоские имена PDF внутри корня: без путей и ссылок наружу."""

    def __init__(self, root: Path) -> None:
        self._root = root.resolve()

    @classmethod
    def from_env(cls) -> LocalDocumentStorage:
        return cls(Path(os.getenv("REFERENCE_DOCUMENT_STORAGE_PATH", _DEFAULT_ROOT)))

    def path(self, filename: str) -> Path | None:
        if not _PDF_FILENAME.fullmatch(filename):
            return None
        candidate = (self._root / filename).resolve()
        if candidate.parent != self._root or not candidate.is_file():
            return None
        return candidate
