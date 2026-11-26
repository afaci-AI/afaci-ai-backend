"""Сборка зависимостей норм: порты → SQL и файловое хранилище (composition root)."""

from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.session import get_db

from ..app import NormsService, ReferenceDocuments
from ..infra.documents import LocalDocumentStorage
from ..infra.sql_repo import SqlNormsRepository
from .presenters import PdfUrl, pdf_url_builder


async def get_norms_service(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> NormsService:
    return NormsService(SqlNormsRepository(db))


def get_reference_documents() -> ReferenceDocuments:
    # Корень читается при каждом запросе: путь задаётся окружением.
    return ReferenceDocuments(LocalDocumentStorage.from_env())


def get_pdf_url(
    request: Request,
    documents: Annotated[ReferenceDocuments, Depends(get_reference_documents)],
) -> PdfUrl:
    return pdf_url_builder(request, documents)
