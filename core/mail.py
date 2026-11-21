"""Отправка транзакционных писем через SMTP (Gmail, Яндекс, локальный Mailpit).

Настройки берутся из окружения при каждой отправке, поэтому тесты и разные
стенды переключают почту без перезапуска модулей. Содержимое писем и пароли
SMTP в лог не пишутся.
"""

from __future__ import annotations

import asyncio
import logging
import os
import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formatdate, make_msgid

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 15


class MailError(Exception):
    """Письмо не отправлено: почта не настроена или SMTP-сервер недоступен."""


@dataclass(frozen=True)
class MailSettings:
    host: str
    port: int
    username: str
    password: str
    sender: str
    security: str  # starttls | ssl | none

    @classmethod
    def from_env(cls) -> MailSettings:
        host = os.getenv("SMTP_HOST", "").strip()
        sender = os.getenv("SMTP_FROM", "").strip()
        if not host or not sender:
            raise MailError("Почта не настроена: задайте SMTP_HOST и SMTP_FROM.")
        security = os.getenv("SMTP_SECURITY", "starttls").strip().lower()
        if security not in {"starttls", "ssl", "none"}:
            raise MailError("SMTP_SECURITY: допустимы starttls, ssl или none.")
        default_port = {"starttls": 587, "ssl": 465, "none": 25}[security]
        return cls(
            host=host,
            port=int(os.getenv("SMTP_PORT") or default_port),
            username=os.getenv("SMTP_USERNAME", "").strip(),
            password=os.getenv("SMTP_PASSWORD", ""),
            sender=sender,
            security=security,
        )


def build_message(
    sender: str, to: str, subject: str, text: str, html: str | None = None
) -> EmailMessage:
    """Текстовая версия обязательна; HTML добавляется альтернативой к ней."""
    message = EmailMessage()
    message["From"] = sender
    message["To"] = to
    message["Subject"] = subject
    message["Date"] = formatdate(localtime=True)
    message["Message-ID"] = make_msgid(domain="afaci")
    message.set_content(text)
    if html:
        message.add_alternative(html, subtype="html")
    return message


def _send_sync(settings: MailSettings, message: EmailMessage) -> None:
    context = ssl.create_default_context()
    if settings.security == "ssl":
        smtp: smtplib.SMTP = smtplib.SMTP_SSL(
            settings.host, settings.port, timeout=TIMEOUT_SECONDS, context=context
        )
    else:
        smtp = smtplib.SMTP(settings.host, settings.port, timeout=TIMEOUT_SECONDS)
    with smtp:
        if settings.security == "starttls":
            smtp.starttls(context=context)
        if settings.username:
            smtp.login(settings.username, settings.password)
        smtp.send_message(message)


class SmtpMailer:
    """Адаптер отправки писем; ошибки SMTP превращаются в MailError."""

    async def send(
        self, to: str, subject: str, text: str, html: str | None = None
    ) -> None:
        settings = MailSettings.from_env()
        message = build_message(settings.sender, to, subject, text, html)
        try:
            await asyncio.to_thread(_send_sync, settings, message)
        except (OSError, smtplib.SMTPException) as exc:
            # Адрес получателя и текст письма не логируем: в письме секрет.
            logger.warning("SMTP: письмо не отправлено (%s)", type(exc).__name__)
            raise MailError("Не удалось отправить письмо.") from exc
