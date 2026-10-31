"""Reference API contracts without reading .env or connecting to the live DB."""

import importlib
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient


async def unused_db():
    raise AssertionError("Contract tests must not connect to a database")


session_stub = ModuleType("infrastructure.db.session")
session_stub.get_db = unused_db
with patch.dict(sys.modules, {"infrastructure.db.session": session_stub}):
    calculator = importlib.import_module("api.v1.calculator")
from api.v1.reference_documents import router as documents_router


class ReferenceSourceChecks(unittest.TestCase):
    def test_sources_external_local_and_unspecified(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "report.pdf").write_bytes(b"%PDF-1.4\n")
            rows = []
            for title, filename in (
                ("Report", "report.pdf"),
                ("Article", None),
                (None, None),
            ):
                rows.append(
                    {
                        "id": uuid4(),
                        "name": "Reference",
                        "year": 1991,
                        "is_default": False,
                        "description": "Description",
                        "source_title": title,
                        "source_authors": "FAO/WHO",
                        "source_year": 1991,
                        "source_location": "Table 7",
                        "source_url": "https://example.org/source" if title else None,
                        "source_pdf_filename": filename,
                    }
                )
            row_result = Mock()
            row_result.mappings.return_value.all.return_value = rows
            value_result = Mock()
            value_result.mappings.return_value.all.return_value = [
                {"amino_acid": "ЛИЗ", "value": 5.8, "sort_order": 1}
            ]
            db = Mock()
            db.execute = AsyncMock(
                side_effect=[row_result] + [value_result] * len(rows)
            )
            app = FastAPI()
            app.include_router(calculator.router)
            app.include_router(documents_router)
            app.dependency_overrides[calculator.get_db] = lambda: db
            with patch.dict(
                "os.environ", {"REFERENCE_DOCUMENT_STORAGE_PATH": directory}
            ):
                response = TestClient(app).get("/api/v1/calculator/reference-proteins")
            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertEqual(
                payload[0]["source"]["pdf_url"],
                "http://testserver/api/v1/calculator/reference-documents/report.pdf",
            )
            self.assertIsNone(payload[1]["source"]["pdf_url"])
            self.assertEqual(payload[1]["source"]["url"], "https://example.org/source")
            self.assertIsNone(payload[2]["source"])
            self.assertEqual(
                payload[0]["values"], [{"amino_acid": "ЛИЗ", "value": 5.8}]
            )
            self.assertNotIn("source_pdf_filename", payload[0])
            spec = app.openapi()
            self.assertIn("ReferenceSourceOut", spec["components"]["schemas"])

    def test_missing_pdf_keeps_external_link(self):
        row = {
            "id": uuid4(),
            "name": "Reference",
            "year": 1991,
            "is_default": False,
            "description": None,
            "source_title": "Report",
            "source_authors": None,
            "source_year": 1991,
            "source_location": None,
            "source_url": "https://example.org/source",
            "source_pdf_filename": "missing.pdf",
        }
        rows, values = Mock(), Mock()
        rows.mappings.return_value.all.return_value = [row]
        values.mappings.return_value.all.return_value = []
        db = Mock()
        db.execute = AsyncMock(side_effect=[rows, values])
        app = FastAPI()
        app.include_router(calculator.router)
        app.dependency_overrides[calculator.get_db] = lambda: db
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.dict("os.environ", {"REFERENCE_DOCUMENT_STORAGE_PATH": directory}),
        ):
            response = TestClient(app).get("/api/v1/calculator/reference-proteins")
        source = response.json()[0]["source"]
        self.assertIsNone(source["pdf_url"])
        self.assertEqual(source["url"], "https://example.org/source")
