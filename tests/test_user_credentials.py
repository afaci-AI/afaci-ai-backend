"""Временный пароль нового пользователя: письмо, повторная отправка, первый вход."""

import re
import unittest
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

from fastapi import HTTPException

from core import mail, security
from core.errors import ConflictError, ForbiddenError, ServiceUnavailableError
from features.auth.app import AuthService
from features.auth.infra.security_adapter import SecurityCredentials
from features.users.app import UserService
from features.users.app.credentials import (
    TEMP_PASSWORD_TTL,
    generate_temp_password,
)
from features.users.infra.sql_repo import BcryptHasher

NOW = datetime(2026, 11, 21, 12, 0, tzinfo=UTC)


class FakeUsers:
    def __init__(self):
        self.rows = {}

    async def find_by_email(self, email):
        return next((u for u in self.rows.values() if u.email == email), None)

    async def get(self, user_id):
        return self.rows.get(user_id)

    async def add(self, data):
        row = SimpleNamespace(
            id=uuid4(), is_active=True, token_version=0, created_at=NOW, **data
        )
        self.rows[row.id] = row
        return row

    async def save(self, row):
        return row


class FakeMailer:
    def __init__(self):
        self.sent = []
        self.fail = False

    async def send(self, to, subject, text, html=None):
        if self.fail:
            raise mail.MailError("down")
        self.sent.append((to, text, html))


class NoAudit:
    def user_updated(self, *args):
        pass


def password_from(text):
    return re.search(r"Временный пароль: (\S+)", text).group(1)


class TemporaryPasswordFlow(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.now = NOW
        self.users = FakeUsers()
        self.mailer = FakeMailer()
        self.service = UserService(
            self.users, BcryptHasher(), NoAudit(), self.mailer, now=lambda: self.now
        )
        self.auth = AuthService(self.users, SecurityCredentials())

    async def create(self):
        return await self.service.create(
            {
                "email": " New@Example.com ",
                "name": "Новый",
                "role": "viewer",
                "access_expires_at": None,
            }
        )

    async def test_create_sends_login_and_temporary_password(self):
        user, delivery = await self.create()
        self.assertEqual(delivery, {"sent": True, "error": None})
        to, text, html = self.mailer.sent[0]
        self.assertEqual(to, "new@example.com")
        self.assertIn("new@example.com", text)
        password = password_from(text)
        self.assertIn(password, html)
        self.assertNotIn(password, user.password_hash)
        self.assertTrue(security.verify_password(password, user.password_hash))
        self.assertTrue(user.must_change_password)
        self.assertEqual(user.temp_password_expires_at, NOW + TEMP_PASSWORD_TTL)

    async def test_mail_failure_keeps_account_and_reports_it(self):
        self.mailer.fail = True
        user, delivery = await self.create()
        self.assertFalse(delivery["sent"])
        self.assertIn(user.id, self.users.rows)

    async def test_resend_replaces_password_without_duplicate(self):
        user, _ = await self.create()
        first = password_from(self.mailer.sent[0][1])
        self.now = NOW + timedelta(hours=1)
        same, delivery = await self.service.resend_credentials(user.id)
        second = password_from(self.mailer.sent[1][1])
        self.assertIs(same, user)
        self.assertEqual(len(self.users.rows), 1)
        self.assertTrue(delivery["sent"])
        self.assertFalse(security.verify_password(first, user.password_hash))
        self.assertTrue(security.verify_password(second, user.password_hash))
        self.assertEqual(user.token_version, 1)
        self.assertEqual(user.temp_password_expires_at, self.now + TEMP_PASSWORD_TTL)

    async def test_resend_mail_failure_keeps_previous_password(self):
        user, _ = await self.create()
        first = password_from(self.mailer.sent[0][1])
        self.mailer.fail = True
        with self.assertRaises(ServiceUnavailableError):
            await self.service.resend_credentials(user.id)
        self.assertTrue(security.verify_password(first, user.password_hash))

    async def test_resend_refused_after_user_set_own_password(self):
        user, _ = await self.create()
        user.must_change_password = False
        with self.assertRaises(ConflictError):
            await self.service.resend_credentials(user.id)

    async def test_first_login_then_change_password(self):
        user, _ = await self.create()
        password = password_from(self.mailer.sent[0][1])
        _, logged = await self.auth.login("new@example.com", password)
        with self.assertRaises(HTTPException) as ctx:
            await security.get_current_user(logged)
        self.assertEqual(ctx.exception.status_code, 403)

        await self.auth.change_password(user, password, "my-own-secret")
        self.assertFalse(user.must_change_password)
        self.assertIsNone(user.temp_password_expires_at)
        self.assertIs(await security.get_current_user(user), user)

    async def test_expired_temporary_password_is_rejected(self):
        user, _ = await self.create()
        password = password_from(self.mailer.sent[0][1])
        user.temp_password_expires_at = datetime.now(UTC) - timedelta(minutes=1)
        with self.assertRaises(ForbiddenError):
            await self.auth.login("new@example.com", password)

    async def test_new_password_must_differ(self):
        user, _ = await self.create()
        password = password_from(self.mailer.sent[0][1])
        from core.errors import BadRequestError

        with self.assertRaises(BadRequestError):
            await self.auth.change_password(user, password, password)


class TemporaryPasswordShape(unittest.TestCase):
    def test_has_letters_and_digits_without_ambiguous_chars(self):
        for _ in range(200):
            password = generate_temp_password()
            self.assertEqual(len(password), 10)
            self.assertTrue(any(c.isdigit() for c in password))
            self.assertTrue(any(c.isalpha() for c in password))
            self.assertFalse(set(password) & set("0O1lI"))


if __name__ == "__main__":
    unittest.main()
