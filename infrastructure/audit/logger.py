"""
Конфигурация аудит-логгера: ротация по времени + дублирование в stdout.

Требования ТЗ:
- директория logs/
- TimedRotatingFileHandler: when="midnight", backupCount=30
- файл logs/audit.log с суффиксом .YYYY-MM-DD (дефолт TimedRotatingFileHandler)
- JSON-формат, уровни INFO(2xx/3xx)/WARNING(4xx)/ERROR(5xx) — уровни ставит middleware
- stdout для отладки
- отказоустойчивость: никогда не ломаем приложение, fallback на stdout

Примечание по масштабированию:
TimedRotatingFileHandler не безопасен при нескольких воркерах (Gunicorn/Uvicorn workers >1).
При масштабировании замените на ConcurrentRotatingFileHandler (pip install concurrent-log-handler)
или агрегируйте логи через внешний сборщик (Loki/ELK/Datadog).
"""

from __future__ import annotations

import json
import logging
import sys
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

AUDIT_LOGGER_NAME = "audit"
LOG_DIR = Path("logs")
LOG_FILE = LOG_DIR / "audit.log"

# Флаг чтобы не настраивать логгер дважды при reload
_configured: bool = False


class JsonAuditFormatter(logging.Formatter):
    """Форматирует LogRecord как одну JSON-строку.

    Ожидает, что message уже JSON (middleware формирует payload).
    Если message не JSON — оборачивает в поле msg.
    Добавляет level для удобства фильтрации.
    """

    def format(self, record: logging.LogRecord) -> str:
        # Сообщение уже может быть JSON-строкой от middleware/helpers
        msg = record.getMessage()
        try:
            payload = json.loads(msg)
            # Добавляем level если его нет в payload
            if isinstance(payload, dict) and "level" not in payload:
                payload["level"] = record.levelname
            return json.dumps(payload, ensure_ascii=False)
        except (json.JSONDecodeError, ValueError):
            # Fallback: структурированный формат
            fallback = {
                "timestamp": self.formatTime(record, datefmt="%Y-%m-%dT%H:%M:%S%z"),
                "level": record.levelname,
                "logger": record.name,
                "msg": msg,
            }
            return json.dumps(fallback, ensure_ascii=False)


def setup_audit_logging() -> logging.Logger:
    """Идемпотентная настройка аудит-логгера. Вызывается из main.py при старте."""
    global _configured

    logger = logging.getLogger(AUDIT_LOGGER_NAME)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if _configured and logger.handlers:
        return logger

    # Очищаем handlers при повторной конфигурации (reload)
    if logger.handlers:
        logger.handlers.clear()

    formatter = JsonAuditFormatter()

    # --- stdout handler (всегда) ---
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(logging.INFO)
    stdout_handler.setFormatter(formatter)
    logger.addHandler(stdout_handler)

    # --- file handler с ротацией ---
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        file_handler = TimedRotatingFileHandler(
            filename=str(LOG_FILE),
            when="midnight",
            interval=1,
            backupCount=30,
            encoding="utf-8",
            utc=True,
        )
        # Дефолт suffix "%Y-%m-%d" → файлы audit.log.2026-08-23
        # Не меняем — это стандарт для утилит сбора логов.
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except (OSError, PermissionError, FileNotFoundError) as exc:
        # Отказоустойчивость: если нет прав на logs/ — остаёмся только на stdout
        logger.warning(
            json.dumps(
                {
                    "timestamp": _utc_now_iso(),
                    "level": "WARNING",
                    "msg": f"Audit file handler not configured: {exc}",
                    "fallback": "stdout_only",
                },
                ensure_ascii=False,
            )
        )

    _configured = True
    return logger


def get_audit_logger() -> logging.Logger:
    """Вернуть настроенный логгер (ленивая инициализация)."""
    logger = logging.getLogger(AUDIT_LOGGER_NAME)
    if not logger.handlers:
        return setup_audit_logging()
    return logger


def _utc_now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()
