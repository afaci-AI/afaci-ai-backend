"""Сценарии управления пользователями (только для администраторов)."""

from __future__ import annotations

from uuid import UUID

from core.errors import BadRequestError, ConflictError, NotFoundError

from ..domain.rules import (
    UserRuleViolation,
    validate_expiry,
    validate_not_self_deactivation,
    validate_not_self_demotion,
    validate_role,
)
from .ports import ChangeAudit, PasswordHasher, Row, UserRepository

NOT_FOUND = "Пользователь не найден."


def _rule(check, *args) -> None:
    try:
        check(*args)
    except UserRuleViolation as exc:
        raise BadRequestError(exc.detail) from exc


class UserService:
    def __init__(
        self, repo: UserRepository, hasher: PasswordHasher, audit: ChangeAudit
    ) -> None:
        self._repo = repo
        self._hasher = hasher
        self._audit = audit

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

    async def create(self, data: dict) -> Row:
        _rule(validate_role, data["role"])
        _rule(validate_expiry, data["access_expires_at"])
        email = data["email"].lower()
        if await self._repo.find_by_email(email) is not None:
            raise ConflictError("Пользователь с таким email уже существует.")
        return await self._repo.add(
            {
                "email": email,
                "name": data["name"].strip(),
                "password_hash": self._hasher.hash(data["password"]),
                "role": data["role"],
                "access_expires_at": data["access_expires_at"],
                "must_change_password": data["must_change_password"],
            }
        )

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
