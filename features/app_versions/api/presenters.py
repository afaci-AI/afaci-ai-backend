"""Представление версий приложения в ответах API."""

from __future__ import annotations


def public(v) -> dict:
    return {
        "version": v.version,
        "versionCode": v.version_code,
        "apkUrl": v.apk_url,
        "changelog": v.changelog,
        "forceUpdate": v.force_update,
        "minSupportedVersionCode": v.min_supported_version_code,
    }


def admin(v) -> dict:
    return {
        "id": v.id,
        "version": v.version,
        "versionCode": v.version_code,
        "apkUrl": v.apk_url,
        "apkFilename": v.apk_filename,
        "changelog": v.changelog,
        "forceUpdate": v.force_update,
        "minSupportedVersionCode": v.min_supported_version_code,
        "isCurrent": v.is_current,
        "publishedAt": v.published_at,
    }
