"""Команды сценариев версий: поля в терминах фичи, без формата API (camelCase)."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class NewAppVersion:
    """Публикуемая версия: APK уже в хранилище либо внешняя ссылка."""

    version: str
    version_code: int
    apk_filename: str
    changelog: str | None = None
    force_update: bool = False
    min_supported_version_code: int | None = None
    is_current: bool = True


@dataclass(frozen=True)
class AppVersionChanges:
    """Правка версии. `None` — «не менять», кроме полей из `provided`:
    `min_supported_version_code`, переданный явно как `None`, сбрасывается."""

    version: str | None = None
    changelog: str | None = None
    force_update: bool | None = None
    min_supported_version_code: int | None = None
    provided: frozenset[str] = field(default_factory=frozenset)
