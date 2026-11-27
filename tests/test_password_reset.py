"""Восстановление пароля по коду: без БД и без реальной почты."""

import os
import unittest
from datetime import timedelta

from core import mail, security
from core.errors import BadRequestError, ServiceUnavailableError
from features.auth.app.password_reset import (
    CODE_TTL,
    INVALID_CODE,
    MAX_ATTEMPTS,
    MAX_CODES_PER_HOUR,
    REQUEST_ACCEPTED,
    RESEND_COOLDOWN,
    PasswordResetService,
)
from features.auth.infra.security_adapter import BcryptPasswords, HmacResetCodes
from tests.account_fakes import (
    NOW,
    FakeAccounts,
    FakeCodes,
    FakeUnitOfWork,
    account_row,
)


class FakeMailer:
    def __init__(self, fail=False):
        self.sent = []
        self.fail = fail

    async def send(self, to, subject, text, html=None):
        if self.fail:
            raise mail.MailError("down")
        self.sent.append((to, subject, text, html))


def make_user(**overrides):
    data = {
        "password_hash": security.hash_password("old-secret"),
        "must_change_password": True,
    }
    data.update(overrides)
    return account_row(**data)


def sent_code(mailer):
    text = mailer.sent[-1][2]
    return next(word for word in text.split() if word.isdigit() and len(word) == 6)


class PasswordResetFlow(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.now = NOW
        self.user = make_user()
        self.accounts = FakeAccounts(self.user)
        self.codes = FakeCodes(lambda: self.now)
        self.mailer = FakeMailer()
        self.uow = FakeUnitOfWork()
        self.service = self.build(self.mailer)

    def build(self, mailer):
        return PasswordResetService(
            self.accounts,
            self.codes,
            self.uow,
            BcryptPasswords(),
            HmacResetCodes(),
            mailer,
            now=lambda: self.now,
        )

    async def test_code_resets_password_once_and_revokes_tokens(self):
        old_token = security.create_access_token(self.user.id, 0)
        result = await self.service.request(" User@Example.com ")
        self.assertEqual(result["message"], REQUEST_ACCEPTED)
        code = sent_code(self.mailer)
        self.assertNotIn(code, self.codes.rows[0].code_hash)

        await self.service.confirm("user@example.com", code, "new-secret")

        self.assertTrue(security.verify_password("new-secret", self.user.password_hash))
        self.assertFalse(
            security.verify_password("old-secret", self.user.password_hash)
        )
        self.assertFalse(self.user.must_change_password)
        self.assertEqual(self.user.token_version, 1)
        _, version = security._decode(old_token)
        self.assertFalse(security.token_is_current(self.user, version))
        with self.assertRaises(BadRequestError):
            await self.service.confirm("user@example.com", code, "another")

    async def test_unknown_and_inactive_addresses_get_same_answer_without_mail(self):
        blocked = make_user(email="off@example.com", is_active=False)
        expired = make_user(
            email="late@example.com", access_expires_at=NOW - timedelta(days=1)
        )
        self.accounts.rows.update({blocked.id: blocked, expired.id: expired})
        for email in ("nobody@example.com", blocked.email, expired.email):
            with self.subTest(email=email):
                result = await self.service.request(email)
                self.assertEqual(result["message"], REQUEST_ACCEPTED)
        self.assertEqual(self.mailer.sent, [])
        self.assertEqual(self.codes.rows, [])

    async def test_verify_checks_code_without_spending_it(self):
        await self.service.request(self.user.email)
        code = sent_code(self.mailer)
        wrong = "000000" if code != "000000" else "111111"
        with self.assertRaises(BadRequestError):
            await self.service.verify(self.user.email, wrong)
        self.assertEqual(self.codes.rows[0].attempts, 1)
        await self.service.verify(self.user.email, code)
        self.assertIsNone(self.codes.rows[0].used_at)
        await self.service.confirm(self.user.email, code, "new-secret")
        self.assertEqual(self.user.token_version, 1)

    async def test_expired_code_is_rejected(self):
        await self.service.request(self.user.email)
        code = sent_code(self.mailer)
        self.now = NOW + CODE_TTL + timedelta(seconds=1)
        with self.assertRaises(BadRequestError) as ctx:
            await self.service.confirm(self.user.email, code, "new-secret")
        self.assertEqual(ctx.exception.detail, INVALID_CODE)

    async def test_wrong_attempts_burn_the_code(self):
        await self.service.request(self.user.email)
        code = sent_code(self.mailer)
        wrong = "000000" if code != "000000" else "111111"
        for _ in range(MAX_ATTEMPTS):
            with self.assertRaises(BadRequestError):
                await self.service.confirm(self.user.email, wrong, "new-secret")
        with self.assertRaises(BadRequestError):
            await self.service.confirm(self.user.email, code, "new-secret")
        self.assertEqual(self.user.token_version, 0)

    async def test_resend_waits_for_cooldown(self):
        result = await self.service.request(self.user.email)
        self.assertEqual(result["resend_after"], RESEND_COOLDOWN.total_seconds())
        self.now = NOW + RESEND_COOLDOWN - timedelta(seconds=1)
        await self.service.request(self.user.email)
        self.assertEqual(len(self.mailer.sent), 1)
        self.now = NOW + RESEND_COOLDOWN
        await self.service.request(self.user.email)
        self.assertEqual(len(self.mailer.sent), 2)

    async def test_new_code_replaces_previous(self):
        await self.service.request(self.user.email)
        first = sent_code(self.mailer)
        self.now = NOW + RESEND_COOLDOWN
        await self.service.request(self.user.email)
        second = sent_code(self.mailer)
        if first != second:
            with self.assertRaises(BadRequestError):
                await self.service.confirm(self.user.email, first, "new-secret")
        await self.service.confirm(self.user.email, second, "new-secret")
        self.assertEqual(self.user.token_version, 1)

    async def test_requests_per_hour_are_limited_silently(self):
        for i in range(MAX_CODES_PER_HOUR + 2):
            self.now = NOW + RESEND_COOLDOWN * i
            result = await self.service.request(self.user.email)
            self.assertEqual(result["message"], REQUEST_ACCEPTED)
        self.assertEqual(len(self.mailer.sent), MAX_CODES_PER_HOUR)

    async def test_mail_failure_is_reported_and_leaves_no_code(self):
        service = self.build(FakeMailer(fail=True))
        with self.assertRaises(ServiceUnavailableError):
            await service.request(self.user.email)
        self.assertEqual(self.codes.rows, [])


class ResetTransactions(PasswordResetFlow):
    """Что именно фиксируется: порядок и границы транзакций сценария."""

    async def test_request_commits_code_then_invalidation(self):
        await self.service.request(self.user.email)
        self.assertEqual(self.uow.calls, ["commit", "commit"])

    async def test_mail_failure_commits_code_then_its_removal(self):
        service = self.build(FakeMailer(fail=True))
        with self.assertRaises(ServiceUnavailableError):
            await service.request(self.user.email)
        self.assertEqual(self.uow.calls, ["commit", "commit"])

    async def test_failed_attempt_is_committed_before_the_error(self):
        await self.service.request(self.user.email)
        self.uow.calls.clear()
        with self.assertRaises(BadRequestError):
            await self.service.confirm(self.user.email, "000000", "new-secret")
        self.assertEqual(self.uow.calls, ["commit"])
        self.assertEqual(self.codes.rows[0].attempts, 1)

    async def test_confirm_spends_code_and_sets_password_separately(self):
        await self.service.request(self.user.email)
        code = sent_code(self.mailer)
        self.uow.calls.clear()
        await self.service.confirm(self.user.email, code, "new-secret")
        self.assertEqual(self.uow.calls, ["commit", "commit"])


class ResetEmailContent(unittest.TestCase):
    def test_html_and_text_carry_code_and_escape_name(self):
        from core.mail_layout import render_html, render_text
        from features.auth.app.password_reset import reset_email

        email = reset_email("<b>Анна</b>", "042517")
        html, text = render_html(email), render_text(email)
        self.assertIn("042517", html)
        self.assertIn("042517", text)
        self.assertIn("&lt;b&gt;Анна&lt;/b&gt;", html)
        self.assertNotIn("<b>Анна</b>", html)

    def test_message_has_text_and_html_parts(self):
        message = mail.build_message("a@x", "b@y", "Тема", "текст", "<p>html</p>")
        types = [part.get_content_type() for part in message.walk()]
        self.assertIn("text/plain", types)
        self.assertIn("text/html", types)


class TokenVersion(unittest.TestCase):
    def test_tokens_without_version_match_initial_version(self):
        import jwt

        user = make_user()
        legacy = jwt.encode(
            {"sub": str(user.id), "exp": NOW + timedelta(days=3650)},
            security.JWT_SECRET,
            algorithm=security.JWT_ALGORITHM,
        )
        _, version = security._decode(legacy)
        self.assertTrue(security.token_is_current(user, version))
        user.token_version = 1
        self.assertFalse(security.token_is_current(user, version))


class MailSettingsFromEnv(unittest.TestCase):
    def setUp(self):
        self.saved = {k: v for k, v in os.environ.items() if k.startswith("SMTP_")}
        for key in list(self.saved):
            del os.environ[key]
        self.addCleanup(self.restore)

    def restore(self):
        for key in [k for k in os.environ if k.startswith("SMTP_")]:
            del os.environ[key]
        os.environ.update(self.saved)

    def test_missing_host_means_mail_is_not_configured(self):
        with self.assertRaises(mail.MailError):
            mail.MailSettings.from_env()

    def test_gmail_defaults_to_starttls_587(self):
        os.environ.update(
            SMTP_HOST="smtp.gmail.com",
            SMTP_FROM="AFACI <a@gmail.com>",
            SMTP_USERNAME="a@gmail.com",
        )
        settings = mail.MailSettings.from_env()
        self.assertEqual((settings.port, settings.security), (587, "starttls"))


if __name__ == "__main__":
    unittest.main()
