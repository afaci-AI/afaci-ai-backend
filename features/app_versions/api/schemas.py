"""Схемы запросов и ответов версий приложения."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class AppVersionPublic(BaseModel):
    version: str
    versionCode: int
    apkUrl: str
    changelog: str | None = None
    forceUpdate: bool
    minSupportedVersionCode: int | None = None


class AppVersionCreate(BaseModel):
    version: str = Field(min_length=1)
    versionCode: int = Field(gt=0)
    apkFilename: str = Field(min_length=1)
    changelog: str | None = None
    forceUpdate: bool = False
    minSupportedVersionCode: int | None = None
    isCurrent: bool = True


class AppVersionUpdate(BaseModel):
    version: str | None = None
    changelog: str | None = None
    forceUpdate: bool | None = None
    minSupportedVersionCode: int | None = None


class AppVersionAdmin(BaseModel):
    id: UUID
    version: str
    versionCode: int
    apkUrl: str
    apkFilename: str
    changelog: str | None
    forceUpdate: bool
    minSupportedVersionCode: int | None
    isCurrent: bool
    publishedAt: datetime
