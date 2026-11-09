"""Upload contract regressions without local settings or a database."""

import io
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.db.session import get_db
from core.errors import register_error_handlers
from core.security import require_admin
from features.app_versions.api import router
from features.app_versions.domain.apk import ApkError
from features.app_versions.infra import adapters

READ_VERSION = "features.app_versions.infra.adapters.AaptInspector.read_version"


class ApkUploadTests(unittest.TestCase):
    def setUp(self):
        self.storage = tempfile.TemporaryDirectory()
        self.addCleanup(self.storage.cleanup)
        self.env_patch = patch.dict(
            "os.environ", {"APK_STORAGE_PATH": self.storage.name}
        )
        self.env_patch.start()
        self.addCleanup(self.env_patch.stop)
        self.db = Mock(execute=AsyncMock(), commit=AsyncMock(), rollback=AsyncMock())
        self.db.execute.return_value = Mock()
        self.db.execute.return_value.scalar_one_or_none.return_value = None

        async def refresh(row):
            row.id = uuid4()
            row.published_at = datetime.now(UTC)

        self.db.refresh = AsyncMock(side_effect=refresh)
        app = FastAPI()
        register_error_handlers(app)
        app.include_router(router)
        app.dependency_overrides[get_db] = lambda: self.db
        app.dependency_overrides[require_admin] = lambda: Mock(role="admin")
        self.client = TestClient(app)
        self.addCleanup(self.client.close)

    def upload(self, **data):
        return self.client.post(
            "/api/v1/admin/app-versions/upload-apk",
            files={"file": ("release.apk", io.BytesIO(b"PK\x03\x04test"))},
            data=data,
        )

    def test_upload_publishes_complete_admin_contract_and_options(self):
        with patch(READ_VERSION, return_value=("1.2.3", 12)):
            response = self.upload(
                forceUpdate="true", changelog="Fix", minSupportedVersionCode="10"
            )
        self.assertEqual(response.status_code, 201, response.text)
        result = response.json()
        self.assertEqual(result["version"], "1.2.3")
        self.assertEqual(result["versionCode"], 12)
        self.assertTrue(result["isCurrent"])
        self.assertTrue(result["forceUpdate"])
        self.assertEqual(result["changelog"], "Fix")
        self.assertEqual(result["minSupportedVersionCode"], 10)
        datetime.fromisoformat(result["publishedAt"])
        self.assertTrue(Path(self.storage.name, result["apkFilename"]).is_file())
        self.db.commit.assert_awaited_once()

    def test_old_version_does_not_publish_or_leave_file(self):
        self.db.execute.return_value.scalar_one_or_none.return_value = 12
        with patch(READ_VERSION, return_value=("1.2.3", 12)):
            response = self.upload()
        self.assertEqual(response.status_code, 400)
        self.assertEqual(list(Path(self.storage.name).iterdir()), [])
        self.db.commit.assert_not_awaited()
        self.db.rollback.assert_awaited_once()

    def test_invalid_manifest_does_not_leave_file(self):
        with patch(READ_VERSION, side_effect=ApkError("Invalid APK")):
            response = self.upload()
        self.assertEqual(response.status_code, 400)
        self.assertEqual(list(Path(self.storage.name).iterdir()), [])
        self.db.commit.assert_not_awaited()

    def test_aapt_metadata_and_invalid_archive(self):
        inspector = adapters.AaptInspector()
        with patch.object(
            adapters.subprocess,
            "run",
            return_value=Mock(
                stdout="package: name='app' versionCode='12' versionName='1.2.3'\n"
            ),
        ):
            self.assertEqual(inspector.read_version("file.apk"), ("1.2.3", 12))
        with (
            patch.object(adapters.subprocess, "run", return_value=Mock(stdout="")),
            self.assertRaises(ApkError),
        ):
            inspector.read_version("file.apk")


if __name__ == "__main__":
    unittest.main()
