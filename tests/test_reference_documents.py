"""Public PDF storage contract checks without local configuration or a DB."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.v1.reference_documents import document_path, router


class ReferenceDocumentChecks(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.env = patch.dict(
            os.environ, {"REFERENCE_DOCUMENT_STORAGE_PATH": str(self.root)}
        )
        self.env.start()
        self.addCleanup(self.env.stop)
        app = FastAPI()
        app.include_router(router)
        self.client = TestClient(app)
        self.addCleanup(self.client.close)

    def test_public_pdf_is_served_with_pdf_content_type(self):
        data = b"%PDF-1.4\n%%EOF\n"
        (self.root / "report-1991.pdf").write_bytes(data)
        response = self.client.get(
            "/api/v1/calculator/reference-documents/report-1991.pdf"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "application/pdf")
        self.assertIn("inline", response.headers["content-disposition"])
        self.assertEqual(response.headers["x-content-type-options"], "nosniff")
        self.assertEqual(response.content, data)

    def test_unknown_file_and_non_pdf_are_not_served(self):
        (self.root / "notes.txt").write_text("private")
        for filename in ("missing.pdf", "notes.txt"):
            with self.subTest(filename=filename):
                response = self.client.get(
                    f"/api/v1/calculator/reference-documents/{filename}"
                )
                self.assertEqual(response.status_code, 404)

    def test_path_traversal_and_absolute_paths_are_rejected(self):
        for filename in (
            "../secret.pdf",
            "/tmp/secret.pdf",
            r"..\secret.pdf",
            "folder/report.pdf",
            ".hidden.pdf",
        ):
            with self.subTest(filename=filename):
                self.assertIsNone(document_path(filename))
        response = self.client.get(
            "/api/v1/calculator/reference-documents/..%2Fsecret.pdf"
        )
        self.assertEqual(response.status_code, 404)

    def test_symlink_outside_storage_and_directory_are_rejected(self):
        with tempfile.TemporaryDirectory() as outside:
            target = Path(outside) / "private.pdf"
            target.write_bytes(b"%PDF-private")
            (self.root / "escape.pdf").symlink_to(target)
            (self.root / "folder.pdf").mkdir()
            for filename in ("escape.pdf", "folder.pdf"):
                with self.subTest(filename=filename):
                    response = self.client.get(
                        f"/api/v1/calculator/reference-documents/{filename}"
                    )
                    self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
