"""Правила учётных записей: роли, срок доступа, защита собственной записи."""

from __future__ import annotations

from datetime import UTC, datetime

VALID_ROLES = {"admin", "editor", "viewer"}


class UserRuleViolation(Exception):
    """Нарушено правило пользователей; `detail` — сообщение для клиента."""

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


def validate_role(role: str) -> None:
    if role not in VALID_ROLES:
        raise UserRuleViolation(f"Недопустимая роль: {role}")


def validate_expiry(expires_at: datetime | None) -> None:
    if expires_at is not None and expires_at <= datetime.now(UTC):
        raise UserRuleViolation("Дата окончания доступа не может быть в прошлом.")


def validate_not_self_demotion(is_self: bool, new_role: str) -> None:
    if is_self and new_role != "admin":
        raise UserRuleViolation("Нельзя понизить роль собственной учётной записи.")


def validate_not_self_deactivation(is_self: bool) -> None:
    if is_self:
        raise UserRuleViolation("Нельзя деактивировать собственную учётную запись.")
