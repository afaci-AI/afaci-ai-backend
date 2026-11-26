"""Публичная выдача локально хранимых PDF документов-источников."""

from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse

from ..app import ReferenceDocuments
from .deps import get_reference_documents

# Путь остаётся под /calculator: на него уже ссылаются выпущенные клиенты.
router = APIRouter(prefix="/api/v1/calculator", tags=["Calculator"])


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
def get_reference_document(
    filename: str,
    documents: Annotated[ReferenceDocuments, Depends(get_reference_documents)],
) -> FileResponse:
    return FileResponse(
        documents.find(filename),
        media_type="application/pdf",
        filename=filename,
        content_disposition_type="inline",
        headers={"X-Content-Type-Options": "nosniff"},
    )
