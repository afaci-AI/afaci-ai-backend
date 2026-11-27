"""Сценарии аутентификации: вход и смена пароля."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

from core.errors import BadRequestError, ForbiddenError, UnauthorizedError
from core.transaction import transaction

from .ports import Account, AccountRepository, PasswordHasher, TokenIssuer, UnitOfWork

EXPIRED = "Срок действия учётной записи истёк. Обратитесь в техническую поддержку."
TEMP_EXPIRED = (
    "Срок временного пароля истёк. Попросите администратора выслать новый "
    "или воспользуйтесь «Забыли пароль?»."
)
SAME_PASSWORD = "Новый пароль должен отличаться от текущего."
WRONG_CREDENTIALS = "Неверный email или пароль."
WRONG_CURRENT = "Неверный текущий пароль."


class AuthService:
    def __init__(
        self,
        repo: AccountRepository,
        uow: UnitOfWork,
        passwords: PasswordHasher,
        tokens: TokenIssuer,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._repo = repo
        self._uow = uow
        self._passwords = passwords
        self._tokens = tokens
        self._now = now

    async def login(self, email: str, password: str) -> tuple[str, Account]:
        """Возвращает (токен, пользователь)."""
        user = await self._repo.find_by_email(email.lower())
        if user is None or not self._passwords.verify(password, user.password_hash):
            raise UnauthorizedError(WRONG_CREDENTIALS)
        if not user.is_active:
            raise ForbiddenError("Учётная запись отключена.")
        now = self._now()
        if user.access_expired(now):
            raise ForbiddenError(EXPIRED)
        temp_until = user.temp_password_expires_at
        if user.must_change_password and temp_until and temp_until <= now:
            raise ForbiddenError(TEMP_EXPIRED)

        async with transaction(self._uow):
            user = await self._repo.record_login(user.id, now)
        return self._tokens.issue(user.id, user.token_version), user

    async def change_password(
        self, user_id: UUID, current_password: str, new_password: str
    ) -> dict:
        user = await self._repo.get(user_id)
        if user is None or not self._passwords.verify(
            current_password, user.password_hash
        ):
            raise UnauthorizedError(WRONG_CURRENT)
        if new_password == current_password:
            raise BadRequestError(SAME_PASSWORD)
        async with transaction(self._uow):
            await self._repo.set_password(
                user.id, self._passwords.hash(new_password), revoke_tokens=False
            )
        return {"status": "ok"}
