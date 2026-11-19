"""Сборка зависимостей отчётов: порт → SQL-реализация."""

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.session import get_db

from ..app import ReportDocument, ReportService
from ..infra.pdf import render_pdf
from ..infra.sql_queries import SqlReportQueries


async def get_report_service(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ReportService:
    return ReportService(SqlReportQueries(db))


def get_pdf_renderer() -> Callable[[ReportDocument], bytes]:
    return render_pdf
