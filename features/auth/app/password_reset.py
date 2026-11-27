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
from core.transaction import transaction

from .ports import (
    Account,
    AccountRepository,
    Mailer,
    MailFailure,
    PasswordHasher,
    ResetCode,
    ResetCodeHasher,
    ResetCodeRepository,
    UnitOfWork,
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
        uow: UnitOfWork,
        passwords: PasswordHasher,
        code_hasher: ResetCodeHasher,
        mailer: Mailer,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._accounts = accounts
        self._codes = codes
        self._uow = uow
        self._passwords = passwords
        self._code_hasher = code_hasher
        self._mailer = mailer
        self._now = now

    async def _eligible(self, email: str) -> Account | None:
        user = await self._accounts.find_by_email(email.strip().lower())
        if user is None or not user.is_active or user.access_expired(self._now()):
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
        async with transaction(self._uow):
            reset = await self._codes.add(
                user.id, self._code_hasher.hash(user.id, code), now + CODE_TTL
            )
        try:
            email = reset_email(user.name, code)
            await self._mailer.send(
                user.email, SUBJECT, render_text(email), render_html(email)
            )
        except MailFailure as exc:
            async with transaction(self._uow):
                await self._codes.delete(reset.id)
            raise ServiceUnavailableError(MAIL_FAILED) from exc
        # Прежние коды перестают действовать только после успешной отправки.
        async with transaction(self._uow):
            await self._codes.invalidate_others(user.id, keep=reset.id, at=now)
        return _accepted()

    async def _matching_code(self, email: str, code: str) -> tuple[Account, ResetCode]:
        """(пользователь, код) или 400; неверный код тратит попытку."""
        user = await self._eligible(email)
        if user is None:
            raise BadRequestError(INVALID_CODE)
        reset = await self._codes.latest_active(user.id, self._now(), MAX_ATTEMPTS)
        if reset is None:
            raise BadRequestError(INVALID_CODE)
        expected = self._code_hasher.hash(user.id, code.strip())
        if not hmac.compare_digest(reset.code_hash, expected):
            # Попытка тратится даже при отказе, поэтому фиксируется до ошибки.
            async with transaction(self._uow):
                await self._codes.add_failed_attempt(reset.id)
            raise BadRequestError(INVALID_CODE)
        return user, reset

    async def verify(self, email: str, code: str) -> dict:
        """Проверка кода перед вводом нового пароля; код остаётся действующим."""
        await self._matching_code(email, code)
        return {"status": "ok"}

    async def confirm(self, email: str, code: str, new_password: str) -> dict:
        user, reset = await self._matching_code(email, code)
        # Сначала код: при сбое на смене пароля он уже не сработает повторно.
        async with transaction(self._uow):
            await self._codes.consume(reset, self._now())
        # Все выданные ранее токены (другие устройства, вкладки) отклоняются.
        async with transaction(self._uow):
            await self._accounts.set_password(
                user.id, self._passwords.hash(new_password), revoke_tokens=True
            )
        return {"status": "ok"}
