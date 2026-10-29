"""APK upload/delete rules without a DB: the session is a mock, APK meta is patched."""

import importlib
import io
import os
import pkgutil
import sys
import tempfile
import unittest
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

from fastapi import HTTPException, UploadFile


async def unused_db():
    raise AssertionError("Tests must not connect to a database")


session_stub = ModuleType("infrastructure.db.session")
session_stub.get_db = unused_db
with patch.dict(sys.modules, {"infrastructure.db.session": session_stub}):
    app_version = importlib.import_module("api.v1.app_version")
    # Mapper configuration needs every model module imported (production does it via routers).
    _models = importlib.import_module("infrastructure.db.models")
    for _m in pkgutil.iter_modules(_models.__path__):
        importlib.import_module(f"infrastructure.db.models.{_m.name}")

APK_BYTES = b"PK\x03\x04" + b"0" * 64


def make_upload(name="app.apk", data=APK_BYTES):
    return UploadFile(filename=name, file=io.BytesIO(data))


def make_db(max_code):
    db = Mock()
    db.execute = AsyncMock(
        return_value=Mock(scalar_one_or_none=Mock(return_value=max_code))
    )
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    db.refresh = AsyncMock()
    return db


class UploadApkChecks(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        patcher = patch.object(app_version, "APK_STORAGE_PATH", self.dir.name)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.dir.cleanup)

    async def upload(self, db, meta, **kwargs):
        with patch.object(app_version, "_read_apk_meta", return_value=meta):
            return await app_version.upload_apk(
                Mock(),
                db,
                kwargs.pop("file", make_upload()),
                **kwargs,
            )

    async def test_higher_version_code_is_saved_as_current(self):
        db = make_db(max_code=3)
        db.refresh = AsyncMock(side_effect=lambda v: setattr(v, "id", uuid4()))
        result = await self.upload(
            db, ("1.4.0", 4), force_update=True, changelog=" fixes "
        )
        self.assertEqual(result["version"], "1.4.0")
        self.assertEqual(result["versionCode"], 4)
        self.assertTrue(result["forceUpdate"])
        self.assertTrue(result["isCurrent"])
        self.assertEqual(result["changelog"], "fixes")
        files = os.listdir(self.dir.name)
        self.assertEqual(files, [result["apkFilename"]])
        db.commit.assert_awaited_once()

    async def test_first_version_is_accepted(self):
        db = make_db(max_code=None)
        db.refresh = AsyncMock(side_effect=lambda v: setattr(v, "id", uuid4()))
        result = await self.upload(db, ("1.0.0", 1))
        self.assertFalse(result["forceUpdate"])

    async def test_not_higher_version_code_is_rejected_and_file_removed(self):
        for code in (3, 2):
            with self.subTest(code=code):
                db = make_db(max_code=3)
                with self.assertRaises(HTTPException) as ctx:
                    await self.upload(db, ("1.3.0", code))
                self.assertEqual(ctx.exception.status_code, 409)
                self.assertEqual(os.listdir(self.dir.name), [])
                db.commit.assert_not_awaited()

    async def test_min_supported_above_version_code_is_rejected(self):
        with self.assertRaises(HTTPException) as ctx:
            await self.upload(
                make_db(None), ("1.0.0", 5), min_supported_version_code=6
            )
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertEqual(os.listdir(self.dir.name), [])

    async def test_invalid_files_are_rejected(self):
        cases = (
            make_upload("app.txt"),
            make_upload(data=b""),
            make_upload(data=b"NOTAZIP" * 10),
        )
        for file in cases:
            with self.subTest(name=file.filename):
                with self.assertRaises(HTTPException) as ctx:
                    await self.upload(make_db(None), ("1.0.0", 1), file=file)
                self.assertEqual(ctx.exception.status_code, 400)
                self.assertEqual(os.listdir(self.dir.name), [])

    async def test_unreadable_manifest_is_rejected(self):
        with self.assertRaises(HTTPException) as ctx:
            await app_version.upload_apk(
                Mock(), make_db(None), make_upload()
            )
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertEqual(os.listdir(self.dir.name), [])


class DeleteVersionChecks(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        patcher = patch.object(app_version, "APK_STORAGE_PATH", self.dir.name)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.dir.cleanup)

    def db_with(self, version, latest):
        db = Mock()
        db.get = AsyncMock(return_value=version)
        db.delete = AsyncMock()
        db.flush = AsyncMock()
        db.commit = AsyncMock()
        db.execute = AsyncMock(
            return_value=Mock(scalar_one_or_none=Mock(return_value=latest))
        )
        return db

    async def test_deleting_current_promotes_highest_code_and_removes_file(self):
        path = os.path.join(self.dir.name, "20260101000000-app.apk")
        open(path, "wb").close()
        version = SimpleNamespace(is_current=True, apk_filename="20260101000000-app.apk")
        previous = SimpleNamespace(is_current=False)
        db = self.db_with(version, previous)
        result = await app_version.delete_app_version(uuid4(), db, Mock())
        self.assertEqual(result, {"status": "deleted"})
        self.assertTrue(previous.is_current)
        self.assertFalse(os.path.exists(path))

    async def test_deleting_old_version_keeps_current(self):
        version = SimpleNamespace(is_current=False, apk_filename="missing.apk")
        db = self.db_with(version, None)
        await app_version.delete_app_version(uuid4(), db, Mock())
        db.execute.assert_not_awaited()

    async def test_external_url_is_not_touched_and_unknown_id_is_404(self):
        version = SimpleNamespace(is_current=False, apk_filename="https://x/y.apk")
        await app_version.delete_app_version(
            uuid4(), self.db_with(version, None), Mock()
        )
        with self.assertRaises(HTTPException) as ctx:
            await app_version.delete_app_version(
                uuid4(), self.db_with(None, None), Mock()
            )
        self.assertEqual(ctx.exception.status_code, 404)


class ApkMetaChecks(unittest.TestCase):
    def test_garbage_archive_raises_400(self):
        with tempfile.NamedTemporaryFile(suffix=".apk") as f:
            f.write(APK_BYTES)
            f.flush()
            with self.assertRaises(HTTPException) as ctx:
                app_version._read_apk_meta(f.name)
        self.assertEqual(ctx.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main()
