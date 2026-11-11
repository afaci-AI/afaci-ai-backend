"""Сценарии аутентификации: вход и смена пароля."""

from __future__ import annotations

from datetime import UTC, datetime

from core.errors import ForbiddenError, UnauthorizedError

from .ports import AccountRepository, Credentials, Row

EXPIRED = "Срок действия учётной записи истёк. Обратитесь в техническую поддержку."


class AuthService:
    def __init__(self, repo: AccountRepository, credentials: Credentials) -> None:
        self._repo = repo
        self._credentials = credentials

    async def login(self, email: str, password: str) -> tuple[str, Row]:
        """Возвращает (токен, пользователь)."""
        user = await self._repo.find_by_email(email.lower())
        if user is None or not self._credentials.verify_password(
            password, user.password_hash
        ):
            raise UnauthorizedError("Неверный email или пароль.")
        if not user.is_active:
            raise ForbiddenError("Учётная запись отключена.")
        if self._credentials.is_expired(user):
            raise ForbiddenError(EXPIRED)

        user.last_login_at = datetime.now(UTC)
        user = await self._repo.save(user)
        return self._credentials.issue_token(user.id), user

    async def change_password(
        self, user: Row, current_password: str, new_password: str
    ) -> dict:
        if not self._credentials.verify_password(current_password, user.password_hash):
            raise UnauthorizedError("Неверный текущий пароль.")
        user.password_hash = self._credentials.hash_password(new_password)
        user.must_change_password = False
        await self._repo.save(user)
        return {"status": "ok"}
