"""Правила APK-файлов: имя, признак архива, разбор версии из вывода aapt."""

from __future__ import annotations

import re

MAX_APK_SIZE = 200 * 1024 * 1024  # 200 МБ
APK_MAGIC = b"PK\x03\x04"
MAX_VERSION_CODE = 2100000000


class ApkError(Exception):
    """Файл не годится для публикации; `status` — HTTP-код для клиента."""

    def __init__(self, detail: str, status: int = 400) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status = status


def has_apk_extension(filename: str | None) -> bool:
    return bool(filename) and filename.lower().endswith(".apk")


def stored_filename(original: str, timestamp: str, token: str) -> str:
    """Имя в хранилище: `<время>-<случайная часть>-<безопасное имя>`."""
    safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", original)
    return f"{timestamp}-{token}-{safe_name}"


def parse_badging(output: str) -> tuple[str, int]:
    """(versionName, versionCode) из строки `package:` вывода `aapt dump badging`."""
    package = next(
        (line for line in output.splitlines() if line.startswith("package:")), ""
    )
    name = re.search(r" versionName='([^']+)'", package)
    code = re.search(r" versionCode='(\d+)'", package)
    if not name or not code or not 0 < int(code[1]) <= MAX_VERSION_CODE:
        raise ApkError("В APK отсутствуют корректные versionName и versionCode.")
    return name[1], int(code[1])


def public_apk_url(base_url: str, apk_filename: str) -> str:
    """Внешняя ссылка остаётся как есть, имя файла — под базовым адресом."""
    if apk_filename.startswith(("http://", "https://")):
        return apk_filename
    return f"{base_url.rstrip('/')}/{apk_filename.lstrip('/')}"
