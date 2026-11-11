"""Сборка зависимостей версий приложения: порты → реализации."""

import os
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.session import get_db

from ..app import AppVersionService
from ..infra.adapters import AaptInspector, FileApkStorage, SqlAppVersionRepository


async def get_app_version_service(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AppVersionService:
    return AppVersionService(
        SqlAppVersionRepository(db),
        FileApkStorage(os.getenv("APK_STORAGE_PATH", "uploads/apk")),
        AaptInspector(),
        os.getenv("APK_BASE_URL", "/static/apk"),
    )
