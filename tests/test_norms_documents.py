"""Документы и записи норм: решения без HTTP, файлов вне корня и строк-словарей."""

import tempfile
import unittest
from pathlib import Path

from core.errors import NotFoundError
from features.norms.api.presenters import present_payload, source_out
from features.norms.app import ReferenceDocuments
from features.norms.domain.records import (
    DailyNorm,
    NormRow,
    NormsPayload,
    RegistrySource,
)
from features.norms.infra.documents import LocalDocumentStorage


class FakeStorage:
    def __init__(self, *names):
        self.names = set(names)

    def path(self, filename):
        return Path("/docs", filename) if filename in self.names else None


class ReferenceDocumentsTests(unittest.TestCase):
    def test_exists_only_for_stored_file(self):
        documents = ReferenceDocuments(FakeStorage("mr.pdf"))
        self.assertTrue(documents.exists("mr.pdf"))
        self.assertFalse(documents.exists("other.pdf"))
        self.assertFalse(documents.exists(None))

    def test_missing_file_is_not_found(self):
        with self.assertRaises(NotFoundError):
            ReferenceDocuments(FakeStorage()).find("mr.pdf")

    def test_local_storage_serves_only_flat_pdf_in_root(self):
        with tempfile.TemporaryDirectory() as root:
            Path(root, "mr.pdf").write_bytes(b"%PDF")
            storage = LocalDocumentStorage(Path(root))
            self.assertEqual(storage.path("mr.pdf"), Path(root, "mr.pdf").resolve())
            self.assertIsNone(storage.path("../mr.pdf"))
            self.assertIsNone(storage.path("missing.pdf"))


class PresenterTests(unittest.TestCase):
    def test_source_gets_link_instead_of_filename(self):
        source = RegistrySource(
            id="1", kind="document", title="МР", pdf_filename="mr.pdf"
        )
        shown = source_out(source, lambda name: f"/docs/{name}")
        self.assertEqual(shown["pdf_url"], "/docs/mr.pdf")
        self.assertNotIn("pdf_filename", shown)

    def test_payload_blocks_are_kept(self):
        row = NormRow(key="fat", name="Жиры", norm=93.0)
        payload = NormsPayload(macro=[row], micro=[], other=[], sources=[], info={})
        shown = present_payload(payload, lambda name: None)
        self.assertEqual(shown["macro"][0]["key"], "fat")
        self.assertEqual(shown["sources"], [])


class DailyNormRecordTests(unittest.TestCase):
    def test_missing_source_stays_empty_not_text_none(self):
        norm = DailyNorm.of(
            {
                "key": "fiber",
                "name": "Волокна",
                "unit": "г",
                "value": 25,
                "source_id": None,
            }
        )
        self.assertIsNone(norm.source_id)
        self.assertEqual(norm.value, 25.0)


if __name__ == "__main__":
    unittest.main()
