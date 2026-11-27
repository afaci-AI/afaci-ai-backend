"""Сценарии версий приложения на фейках: команды фичи, часы и проверки публикации."""

import unittest
from dataclasses import asdict
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
from features.app_versions.app.ports import StoredApk
from features.app_versions.domain.apk import APK_MAGIC

NOW = datetime(2026, 11, 27, 12, 0, tzinfo=UTC)


class FakeVersions:
    def __init__(self, max_code=None, row=None):
        self.max_code = max_code
        self.row = row
        self.added = None
        self.cleared = False
        self.saved = False

    async def lock_publication(self):
        pass

    async def max_version_code(self):
        return self.max_code

    async def clear_current(self):
        self.cleared = True

    async def add(self, record):
        self.added = record
        return SimpleNamespace(id=uuid4(), **asdict(record))

    async def get(self, version_id):
        return self.row

    async def save(self, row):
        self.saved = True
        return row

    async def delete(self, row):
        pass


class FakeUnitOfWork:
    def __init__(self):
        self.calls = []

    async def commit(self):
        self.calls.append("commit")

    async def rollback(self):
        self.calls.append("rollback")

    async def refresh(self, row):
        self.calls.append("refresh")


class FakeStorage:
    def __init__(self, files=()):
        self.files = set(files)

    def exists(self, filename):
        return filename in self.files


def service(repo, storage=None, uow=None):
    return AppVersionService(
        repo,
        uow or FakeUnitOfWork(),
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
        self.assertEqual(repo.added.apk_url, url)
        self.assertEqual(repo.added.published_at, NOW)
        self.assertTrue(repo.cleared)

    async def test_not_current_keeps_existing_current(self):
        repo = FakeVersions()
        await service(repo, FakeStorage({"app.apk"})).create(command(is_current=False))
        self.assertFalse(repo.cleared)
        self.assertEqual(repo.added.apk_url, "/static/apk/app.apk")


class Transactions(unittest.IsolatedAsyncioTestCase):
    async def test_publish_commits_then_refreshes(self):
        uow = FakeUnitOfWork()
        await service(FakeVersions(), FakeStorage({"app.apk"}), uow).create(command())
        self.assertEqual(uow.calls, ["commit", "refresh"])

    async def test_rejected_publication_rolls_back(self):
        uow = FakeUnitOfWork()
        with self.assertRaises(BadRequestError):
            await service(
                FakeVersions(max_code=12), FakeStorage({"app.apk"}), uow
            ).create(command())
        self.assertEqual(uow.calls, ["rollback"])

    async def test_update_commits_then_refreshes(self):
        uow = FakeUnitOfWork()
        row = SimpleNamespace(
            version="1",
            changelog=None,
            force_update=False,
            min_supported_version_code=None,
        )
        await service(FakeVersions(row=row), uow=uow).update(
            uuid4(), AppVersionChanges(version="2")
        )
        self.assertEqual((row.version, uow.calls), ("2", ["commit", "refresh"]))


class UploadFlow(unittest.IsolatedAsyncioTestCase):
    def build(self, storage, inspector, repo=None):
        return AppVersionService(
            repo or FakeVersions(),
            FakeUnitOfWork(),
            storage,
            inspector,
            apk_base_url="/static/apk",
            now=lambda: NOW,
        )

    async def upload(self, service):
        return await service.upload(
            original_name="release.apk",
            read_chunk=None,
            force_update=False,
            changelog=None,
            min_supported_version_code=None,
        )

    async def test_empty_file_is_removed_and_rejected(self):
        storage = UploadStorage(StoredApk("f.apk", "/p/f.apk", 0, b""))
        with self.assertRaises(BadRequestError):
            await self.upload(self.build(storage, FakeInspector()))
        self.assertEqual(storage.removed, ["/p/f.apk"])

    async def test_failed_publication_removes_stored_file(self):
        storage = UploadStorage(StoredApk("f.apk", "/p/f.apk", 9, APK_MAGIC))
        repo = FakeVersions(max_code=12)
        with self.assertRaises(BadRequestError):
            await self.upload(self.build(storage, FakeInspector(("1.0", 12)), repo))
        self.assertEqual(storage.removed, ["/p/f.apk"])

    async def test_valid_file_is_published_and_kept(self):
        storage = UploadStorage(StoredApk("f.apk", "/p/f.apk", 9, APK_MAGIC))
        storage.files.add("f.apk")
        row = await self.upload(self.build(storage, FakeInspector(("1.0", 5))))
        self.assertEqual((row.version, row.version_code), ("1.0", 5))
        self.assertEqual(storage.removed, [])


class UploadStorage(FakeStorage):
    def __init__(self, stored):
        super().__init__()
        self.stored = stored
        self.removed = []

    async def store(self, original_name, read_chunk):
        return self.stored

    def remove(self, path):
        self.removed.append(path)


class FakeInspector:
    def __init__(self, result=("1.0", 1)):
        self.result = result

    def read_version(self, path):
        return self.result


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
