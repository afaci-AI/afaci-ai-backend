"""Сценарии управления пользователями (только для администраторов)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

from core.errors import (
    BadRequestError,
    ConflictError,
    NotFoundError,
    ServiceUnavailableError,
)
from core.mail_layout import render_html, render_text

from ..domain.rules import (
    UserRuleViolation,
    validate_expiry,
    validate_not_self_deactivation,
    validate_not_self_demotion,
    validate_role,
)
from .credentials import (
    SUBJECT,
    TEMP_PASSWORD_TTL,
    generate_temp_password,
    welcome_email,
)
from .ports import (
    ChangeAudit,
    Mailer,
    MailFailure,
    PasswordHasher,
    Row,
    UserRepository,
)

NOT_FOUND = "Пользователь не найден."
MAIL_FAILED = "Письмо не отправлено: почтовый сервер недоступен или не настроен."
ALREADY_ACTIVATED = (
    "Пользователь уже задал собственный пароль. Для сброса пусть "
    "воспользуется «Забыли пароль?» на экране входа."
)


def _rule(check, *args) -> None:
    try:
        check(*args)
    except UserRuleViolation as exc:
        raise BadRequestError(exc.detail) from exc


class UserService:
    def __init__(
        self,
        repo: UserRepository,
        hasher: PasswordHasher,
        audit: ChangeAudit,
        mailer: Mailer | None = None,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._repo = repo
        self._hasher = hasher
        self._audit = audit
        self._mailer = mailer
        self._now = now

    async def _send_credentials(self, user: Row, password: str) -> dict:
        """Отправка письма; результат отдельно от создания аккаунта."""
        if self._mailer is None:
            return {"sent": False, "error": MAIL_FAILED}
        email = welcome_email(user.name, user.email, password)
        try:
            await self._mailer.send(
                user.email, SUBJECT, render_text(email), render_html(email)
            )
        except MailFailure:
            return {"sent": False, "error": MAIL_FAILED}
        return {"sent": True, "error": None}

    async def _get(self, user_id: UUID) -> Row:
        user = await self._repo.get(user_id)
        if not user:
            raise NotFoundError(NOT_FOUND)
        return user

    async def list(self, role: str | None, search: str | None) -> list[Row]:
        users = await self._repo.list(role)
        if search:
            s = search.lower()
            users = [u for u in users if s in u.email.lower() or s in u.name.lower()]
        return users

    async def get(self, user_id: UUID) -> Row:
        return await self._get(user_id)

    async def create(self, data: dict) -> tuple[Row, dict]:
        """Аккаунт с временным паролем и письмом. Сбой почты аккаунт не отменяет."""
        _rule(validate_role, data["role"])
        _rule(validate_expiry, data["access_expires_at"])
        email = data["email"].strip().lower()
        if await self._repo.find_by_email(email) is not None:
            raise ConflictError("Пользователь с таким email уже существует.")
        password = generate_temp_password()
        user = await self._repo.add(
            {
                "email": email,
                "name": data["name"].strip(),
                "password_hash": self._hasher.hash(password),
                "role": data["role"],
                "access_expires_at": data["access_expires_at"],
                "must_change_password": True,
                "temp_password_expires_at": self._now() + TEMP_PASSWORD_TTL,
            }
        )
        return user, await self._send_credentials(user, password)

    async def resend_credentials(self, user_id: UUID) -> tuple[Row, dict]:
        """Новый временный пароль взамен прежнего; без письма ничего не меняется."""
        user = await self._get(user_id)
        if not user.must_change_password:
            raise ConflictError(ALREADY_ACTIVATED)
        if not user.is_active:
            raise BadRequestError("Учётная запись отключена.")
        password = generate_temp_password()
        delivery = await self._send_credentials(user, password)
        if not delivery["sent"]:
            raise ServiceUnavailableError(MAIL_FAILED)
        user.password_hash = self._hasher.hash(password)
        user.temp_password_expires_at = self._now() + TEMP_PASSWORD_TTL
        # Сессии, открытые прежним временным паролем, завершаются.
        user.token_version = (user.token_version or 0) + 1
        return await self._repo.save(user), delivery

    async def update(self, user_id: UUID, changes: dict, admin_id: UUID) -> Row:
        """changes — поля запроса, переданные клиентом (exclude_unset)."""
        user = await self._get(user_id)
        is_self = user.id == admin_id

        role = changes.get("role")
        if role is not None:
            _rule(validate_role, role)
            _rule(validate_not_self_demotion, is_self, role)
            user.role = role

        is_active = changes.get("is_active")
        if is_active is not None:
            if not is_active:
                _rule(validate_not_self_deactivation, is_self)
            user.is_active = is_active

        if changes.get("name") is not None:
            user.name = changes["name"].strip()

        if changes.get("access_expires_at_unlimited"):
            user.access_expires_at = None
        elif changes.get("access_expires_at") is not None:
            _rule(validate_expiry, changes["access_expires_at"])
            user.access_expires_at = changes["access_expires_at"]

        user = await self._repo.save(user)
        self._audit.user_updated(admin_id, user, user_id, changes)
        return user

    async def deactivate(self, user_id: UUID, admin_id: UUID) -> dict:
        _rule(validate_not_self_deactivation, user_id == admin_id)
        user = await self._get(user_id)
        user.is_active = False
        await self._repo.save(user)
        return {"status": "deactivated"}
