"""Сценарии версий приложения на фейках: команды фичи, часы и проверки публикации."""

import unittest
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

from core.errors import BadRequestError
from features.app_versions.api.schemas import AppVersionCreate, AppVersionUpdate
from features.app_versions.app import (
    AppVersionChanges,
    AppVersionService,
    NewAppVersion,
)

NOW = datetime(2026, 11, 27, 12, 0, tzinfo=UTC)


class FakeVersions:
    def __init__(self, max_code=None, row=None):
        self.max_code = max_code
        self.row = row
        self.added = None
        self.cleared = False

    async def lock_publication(self):
        pass

    async def max_version_code(self):
        return self.max_code

    async def clear_current(self):
        self.cleared = True

    async def add(self, data):
        self.added = data
        return SimpleNamespace(id=uuid4(), **data)

    async def get(self, version_id):
        return self.row

    async def save(self, row):
        return row


class FakeStorage:
    def __init__(self, files=()):
        self.files = set(files)

    def exists(self, filename):
        return filename in self.files


def service(repo, storage=None):
    return AppVersionService(
        repo,
        storage or FakeStorage(),
        inspector=None,
        apk_base_url="/static/apk",
        now=lambda: NOW,
    )


def command(**fields):
    data = {"version": "1.2.0", "version_code": 12, "apk_filename": "app.apk"}
    return NewAppVersion(**{**data, **fields})


class PublishChecks(unittest.IsolatedAsyncioTestCase):
    async def test_version_code_must_grow(self):
        repo = FakeVersions(max_code=12)
        with self.assertRaises(BadRequestError):
            await service(repo, FakeStorage({"app.apk"})).create(command())
        self.assertIsNone(repo.added)

    async def test_missing_stored_apk_is_rejected(self):
        repo = FakeVersions()
        with self.assertRaises(BadRequestError):
            await service(repo).create(command())
        self.assertIsNone(repo.added)

    async def test_external_url_skips_storage_and_uses_clock(self):
        repo = FakeVersions(max_code=11)
        url = "https://cdn.example/app.apk"
        await service(repo).create(command(apk_filename=url))
        self.assertEqual(repo.added["apk_url"], url)
        self.assertEqual(repo.added["published_at"], NOW)
        self.assertTrue(repo.cleared)

    async def test_not_current_keeps_existing_current(self):
        repo = FakeVersions()
        await service(repo, FakeStorage({"app.apk"})).create(command(is_current=False))
        self.assertFalse(repo.cleared)
        self.assertEqual(repo.added["apk_url"], "/static/apk/app.apk")


class UpdateChecks(unittest.IsolatedAsyncioTestCase):
    def row(self):
        return SimpleNamespace(
            version="1.0",
            changelog="old",
            force_update=False,
            min_supported_version_code=5,
        )

    async def test_omitted_fields_stay_and_explicit_null_clears_minimum(self):
        row = self.row()
        changes = AppVersionChanges(
            changelog="new",
            provided=frozenset({"changelog", "min_supported_version_code"}),
        )
        await service(FakeVersions(row=row)).update(uuid4(), changes)
        self.assertEqual((row.version, row.changelog), ("1.0", "new"))
        self.assertIsNone(row.min_supported_version_code)

    async def test_minimum_not_provided_is_kept(self):
        row = self.row()
        await service(FakeVersions(row=row)).update(
            uuid4(),
            AppVersionChanges(force_update=True, provided=frozenset({"force_update"})),
        )
        self.assertTrue(row.force_update)
        self.assertEqual(row.min_supported_version_code, 5)


class SchemaMapping(unittest.TestCase):
    def test_create_schema_maps_to_command(self):
        schema = AppVersionCreate(
            version="1.2.0", versionCode=12, apkFilename="app.apk", forceUpdate=True
        )
        self.assertEqual(schema.command(), command(force_update=True))

    def test_update_schema_reports_provided_fields_in_snake_case(self):
        changes = AppVersionUpdate(
            minSupportedVersionCode=None, changelog="x"
        ).changes()
        self.assertEqual(
            changes.provided, frozenset({"min_supported_version_code", "changelog"})
        )


if __name__ == "__main__":
    unittest.main()
