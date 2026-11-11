"""Public read-only access to locally stored reference-protein documents."""

import os
import re
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse

router = APIRouter(prefix="/api/v1/calculator", tags=["Calculator"])
_PDF_FILENAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\.pdf", re.IGNORECASE)


def document_path(filename: str) -> Path | None:
    """Resolve only a flat PDF filename within the configured storage root."""
    if not _PDF_FILENAME.fullmatch(filename):
        return None
    root = Path(
        os.getenv("REFERENCE_DOCUMENT_STORAGE_PATH", "uploads/reference-documents")
    ).resolve()
    candidate = (root / filename).resolve()
    if candidate.parent != root or not candidate.is_file():
        return None
    return candidate


def pdf_url_builder(request: Request):
    """Ссылка на локально хранимый PDF источника или None, если файла нет."""

    def build(filename: str | None) -> str | None:
        if filename and document_path(filename) is not None:
            return str(request.url_for("get_reference_document", filename=filename))
        return None

    return build


@router.get(
    "/reference-documents/{filename}",
    name="get_reference_document",
    summary="PDF документа-источника эталонного белка",
    response_class=FileResponse,
    responses={
        200: {"content": {"application/pdf": {}}},
        404: {"description": "Документ не найден"},
    },
)
def get_reference_document(filename: str) -> FileResponse:
    path = document_path(filename)
    if path is None:
        raise HTTPException(status_code=404, detail="Документ не найден")
    return FileResponse(
        path,
        media_type="application/pdf",
        filename=filename,
        content_disposition_type="inline",
        headers={"X-Content-Type-Options": "nosniff"},
    )
