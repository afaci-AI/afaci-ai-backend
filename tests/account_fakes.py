"""Хранилища учётных записей и кодов восстановления в памяти для тестов auth и users.

Записи хранятся изменяемыми, а наружу, как и SQL-хранилища, отдаются
неизменяемые снимки `Account` и `ResetCode`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

from core.accounts import Account
from core.db.text_filters import normalize_search_text
from features.auth.app.ports import ResetCode

NOW = datetime(2026, 11, 21, 12, 0, tzinfo=UTC)


def account_row(**overrides) -> SimpleNamespace:
    data = {
        "id": uuid4(),
        "email": "user@example.com",
        "name": "Анна",
        "role": "viewer",
        "password_hash": "",
        "is_active": True,
        "access_expires_at": None,
        "must_change_password": False,
        "temp_password_expires_at": None,
        "token_version": 0,
        "created_at": NOW,
        "last_login_at": None,
    }
    data.update(overrides)
    return SimpleNamespace(**data)


class FakeAccounts:
    """Реализует и `AccountRepository` (auth), и `UserRepository` (users)."""

    def __init__(self, *rows):
        self.rows = {r.id: r for r in rows}
        self.list_calls: list[dict] = []

    def row(self, user_id) -> SimpleNamespace:
        return self.rows[user_id]

    def _by_email(self, email):
        return next((r for r in self.rows.values() if r.email == email), None)

    async def find_by_email(self, email):
        row = self._by_email(email)
        return Account.of(row) if row else None

    async def get(self, user_id):
        row = self.rows.get(user_id)
        return Account.of(row) if row else None

    async def list(self, *, role=None, search=None):
        self.list_calls.append({"role": role, "search": search})
        rows = [r for r in self.rows.values() if role is None or r.role == role]
        if search:
            needle = normalize_search_text(search)
            rows = [
                r
                for r in rows
                if needle in normalize_search_text(r.email)
                or needle in normalize_search_text(r.name)
            ]
        return [Account.of(r) for r in rows]

    async def record_login(self, user_id, at):
        self.rows[user_id].last_login_at = at
        return Account.of(self.rows[user_id])

    async def set_password(self, user_id, password_hash, *, revoke_tokens):
        row = self.rows[user_id]
        row.password_hash = password_hash
        row.must_change_password = False
        row.temp_password_expires_at = None
        if revoke_tokens:
            row.token_version += 1

    async def add(self, new):
        row = account_row(
            email=new.email,
            name=new.name,
            password_hash=new.password_hash,
            role=new.role,
            access_expires_at=new.access_expires_at,
            must_change_password=True,
            temp_password_expires_at=new.temp_password_expires_at,
        )
        self.rows[row.id] = row
        return Account.of(row)

    async def update(self, user_id, edit):
        row = self.rows[user_id]
        row.role, row.is_active = edit.role, edit.is_active
        row.name, row.access_expires_at = edit.name, edit.access_expires_at
        return Account.of(row)

    async def set_temp_password(self, user_id, password_hash, expires_at):
        row = self.rows[user_id]
        row.password_hash = password_hash
        row.temp_password_expires_at = expires_at
        row.token_version += 1
        return Account.of(row)


def _code(row) -> ResetCode:
    return ResetCode(
        id=row.id, user_id=row.user_id, code_hash=row.code_hash, attempts=row.attempts
    )


class FakeCodes:
    def __init__(self, clock=lambda: NOW):
        self.rows = []
        self.clock = clock

    def _find(self, code_id):
        return next(r for r in self.rows if r.id == code_id)

    async def count_since(self, user_id, since):
        return sum(
            1 for r in self.rows if r.user_id == user_id and r.created_at > since
        )

    async def add(self, user_id, code_hash, expires_at):
        row = SimpleNamespace(
            id=uuid4(),
            user_id=user_id,
            code_hash=code_hash,
            expires_at=expires_at,
            attempts=0,
            used_at=None,
            created_at=self.clock(),
        )
        self.rows.append(row)
        return _code(row)

    async def delete(self, code_id):
        self.rows.remove(self._find(code_id))

    async def latest_active(self, user_id, now, max_attempts):
        active = [
            r
            for r in self.rows
            if r.user_id == user_id
            and r.used_at is None
            and r.expires_at > now
            and r.attempts < max_attempts
        ]
        return _code(active[-1]) if active else None

    async def add_failed_attempt(self, code_id):
        self._find(code_id).attempts += 1

    async def invalidate_others(self, user_id, keep, at):
        for r in self.rows:
            if r.user_id == user_id and r.id != keep and r.used_at is None:
                r.used_at = at

    async def consume(self, code, at):
        for r in self.rows:
            if r.user_id == code.user_id and r.used_at is None:
                r.used_at = at
