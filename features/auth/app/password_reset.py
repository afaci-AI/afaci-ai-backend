"""Восстановление пароля одноразовым 6-значным кодом из письма.

Публичный ответ на запрос кода одинаков для известного, неизвестного и
отключённого адреса. Исключение — сбой почты: тогда 503, чтобы не
подтверждать доставку, которой не было.
"""

from __future__ import annotations

import hmac
import secrets
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from core.errors import BadRequestError, ServiceUnavailableError
from core.mail_layout import Email, render_html, render_text

from .ports import (
    AccountRepository,
    Credentials,
    Mailer,
    MailFailure,
    ResetCodeRepository,
    Row,
)

CODE_TTL = timedelta(minutes=30)
MAX_ATTEMPTS = 5
MAX_CODES_PER_HOUR = 5
# Пауза перед повторным письмом; клиенты показывают обратный отсчёт.
RESEND_COOLDOWN = timedelta(seconds=60)

REQUEST_ACCEPTED = (
    "Если адрес зарегистрирован, на него отправлен код. Проверьте почту, "
    "в том числе папку «Спам»."
)
INVALID_CODE = "Неверный или истёкший код. Запросите новый."
MAIL_FAILED = "Не удалось отправить письмо. Попробуйте позже."

SUBJECT = "AFACI: код для восстановления пароля"


def _accepted() -> dict:
    """Одинаковый ответ для любого адреса, включая паузу до повторной отправки."""
    return {
        "status": "ok",
        "message": REQUEST_ACCEPTED,
        "resend_after": int(RESEND_COOLDOWN.total_seconds()),
    }


def reset_email(name: str, code: str) -> Email:
    minutes = int(CODE_TTL.total_seconds() // 60)
    return Email(
        title="Восстановление пароля",
        greeting=f"Здравствуйте, {name}!",
        intro="Вы запросили восстановление пароля в AFACI. Введите этот код "
        "на экране «Забыли пароль?» в приложении или на сайте.",
        highlight=code,
        highlight_label="Код подтверждения",
        notes=[
            f"Код действует {minutes} минут и подходит только один раз.",
            "Никому не сообщайте код: сотрудники AFACI его не спрашивают.",
        ],
        footer="Если вы не запрашивали восстановление, просто проигнорируйте "
        "это письмо: пароль не изменится.",
        preheader=f"Код для восстановления пароля: {code}",
    )


def _new_code() -> str:
    return f"{secrets.randbelow(10**6):06d}"


class PasswordResetService:
    def __init__(
        self,
        accounts: AccountRepository,
        codes: ResetCodeRepository,
        credentials: Credentials,
        mailer: Mailer,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._accounts = accounts
        self._codes = codes
        self._credentials = credentials
        self._mailer = mailer
        self._now = now

    async def _eligible(self, email: str) -> Row | None:
        user = await self._accounts.find_by_email(email.strip().lower())
        if user is None or not user.is_active or self._credentials.is_expired(user):
            return None
        return user

    async def request(self, email: str) -> dict:
        user = await self._eligible(email)
        now = self._now()
        if user is None:
            return _accepted()
        if await self._codes.count_since(user.id, now - timedelta(hours=1)) >= (
            MAX_CODES_PER_HOUR
        ):
            # Лимит на адрес: ответ тот же, письмо не отправляется.
            return _accepted()
        if await self._codes.count_since(user.id, now - RESEND_COOLDOWN):
            # Пауза между письмами не прошла: действует уже отправленный код.
            return _accepted()

        code = _new_code()
        row = await self._codes.add(
            user.id, self._credentials.hash_reset_code(user.id, code), now + CODE_TTL
        )
        try:
            email = reset_email(user.name, code)
            await self._mailer.send(
                user.email, SUBJECT, render_text(email), render_html(email)
            )
        except MailFailure as exc:
            await self._codes.delete(row)
            raise ServiceUnavailableError(MAIL_FAILED) from exc
        # Прежние коды перестают действовать только после успешной отправки.
        await self._codes.invalidate_others(user.id, keep=row.id, at=now)
        return _accepted()

    async def _matching_code(self, email: str, code: str) -> tuple[Row, Row]:
        """(пользователь, код) или 400; неверный код тратит попытку."""
        user = await self._eligible(email)
        if user is None:
            raise BadRequestError(INVALID_CODE)
        row = await self._codes.latest_active(user.id, self._now(), MAX_ATTEMPTS)
        if row is None:
            raise BadRequestError(INVALID_CODE)
        expected = self._credentials.hash_reset_code(user.id, code.strip())
        if not hmac.compare_digest(row.code_hash, expected):
            row.attempts += 1
            await self._codes.save(row)
            raise BadRequestError(INVALID_CODE)
        return user, row

    async def verify(self, email: str, code: str) -> dict:
        """Проверка кода перед вводом нового пароля; код остаётся действующим."""
        await self._matching_code(email, code)
        return {"status": "ok"}

    async def confirm(self, email: str, code: str, new_password: str) -> dict:
        user, row = await self._matching_code(email, code)
        now = self._now()
        row.used_at = now
        user.password_hash = self._credentials.hash_password(new_password)
        user.must_change_password = False
        user.temp_password_expires_at = None
        # Все выданные ранее токены (другие устройства, вкладки) отклоняются.
        user.token_version = (user.token_version or 0) + 1
        await self._codes.invalidate_others(user.id, keep=row.id, at=now)
        await self._accounts.save(user)
        return {"status": "ok"}
