"""Схемы запросов и ответов версий приложения."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from ..app import AppVersionChanges, NewAppVersion


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

    def command(self) -> NewAppVersion:
        return NewAppVersion(
            version=self.version,
            version_code=self.versionCode,
            apk_filename=self.apkFilename,
            changelog=self.changelog,
            force_update=self.forceUpdate,
            min_supported_version_code=self.minSupportedVersionCode,
            is_current=self.isCurrent,
        )


class AppVersionUpdate(BaseModel):
    version: str | None = None
    changelog: str | None = None
    forceUpdate: bool | None = None
    minSupportedVersionCode: int | None = None

    def changes(self) -> AppVersionChanges:
        provided = frozenset(
            _SNAKE_CASE.get(name, name) for name in self.model_fields_set
        )
        return AppVersionChanges(
            version=self.version,
            changelog=self.changelog,
            force_update=self.forceUpdate,
            min_supported_version_code=self.minSupportedVersionCode,
            provided=provided,
        )


_SNAKE_CASE = {
    "forceUpdate": "force_update",
    "minSupportedVersionCode": "min_supported_version_code",
}


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
