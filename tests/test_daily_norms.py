"""Daily norms and sources: domain rules, seeded values and API shapes (no database)."""

import importlib.util
import sys
import unittest
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

from fastapi import FastAPI

from core.errors import NotFoundError
from features.calculator.domain import compute_report
from features.calculator.domain.formulas import energy_kcal
from features.norms.app import NormsService
from features.norms.domain.daily_norms import (
    NORM_ORDER,
    NORMS_INFO,
    amounts_from_macros,
    build_norm_rows,
    percent_of_norm,
)
from features.norms.domain.sources import merge_sources
from features.norms.infra.sql_repo import SqlNormsRepository

MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "c9d0e1f2a3b4_add_sources_and_daily_norms.py"
)

# МР 2.3.1.0253-21, табл. 9 (мужчины) и 14 (женщины), возрасты 18–29 / 30–44 / 45–64
# для групп физической активности 1–4: (энергия ккал, белок г, жиры г, углеводы г).
MEN = [
    (2400, 84, 80, 336), (2300, 81, 77, 322), (2150, 75, 72, 301),
    (2750, 89, 92, 392), (2650, 86, 88, 378), (2450, 80, 82, 349),
    (3250, 102, 108, 467), (3150, 98, 105, 453), (2900, 91, 97, 417),
    (3800, 114, 127, 551), (3650, 110, 122, 529), (3400, 102, 113, 493),
]  # fmt: skip
WOMEN = [
    (1900, 67, 63, 266), (1800, 63, 60, 252), (1700, 60, 57, 238),
    (2200, 72, 73, 314), (2100, 68, 70, 299), (1950, 63, 65, 278),
    (2600, 81, 87, 374), (2500, 78, 83, 359), (2300, 72, 77, 331),
    (3000, 90, 100, 435), (2850, 86, 95, 413), (2700, 81, 90, 392),
]  # fmt: skip


def load_migration():
    spec = importlib.util.spec_from_file_location("norms_migration", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeResult:
    def __init__(self, rows):
        self.rows = rows

    def mappings(self):
        return SimpleNamespace(all=lambda: self.rows)


class DomainTests(unittest.TestCase):
    def test_energy_uses_document_coefficients(self):
        self.assertEqual(energy_kcal(10, 5, 20), 4 * 10 + 9 * 5 + 4 * 20)
        self.assertIsNone(energy_kcal(None, 5, 20))
        self.assertIsNone(energy_kcal(10, None, 20))
        self.assertIsNone(energy_kcal(10, 5, None))

    def test_calculator_energy_matches_shared_formula(self):
        item = {
            "product_id": "1",
            "name": "x",
            "amount_g": 100.0,
            "chem": {
                "Массовая доля белка": 10.0,
                "Массовая доля жира": 5.0,
                "Углеводы": 20.0,
                "Пищевые волокна": 2.0,
            },
            "amino": {},
        }
        reference = {"id": "r", "name": "R", "values": {}}
        report = compute_report([item], reference, rounded=False)
        self.assertEqual(report["energy_kcal"], energy_kcal(10.0, 5.0, 20.0))

    def test_percent_rounding_and_missing_values(self):
        self.assertEqual(percent_of_norm(83, 83), 100.0)
        self.assertEqual(percent_of_norm(41.5, 83), 50.0)
        self.assertEqual(percent_of_norm(1, 3), 33.3)
        self.assertIsNone(percent_of_norm(None, 83))
        self.assertIsNone(percent_of_norm(5, 0))

    def test_rows_follow_fixed_order_and_skip_unknown_norms(self):
        norms = [
            {"key": "fiber", "name": "Волокна", "unit": "г", "value": 25},
            {"key": "energy", "name": "Энергия", "unit": "ккал", "value": 2602},
            {"key": "other", "name": "Другое", "unit": "г", "value": 1},
        ]
        rows = build_norm_rows(norms, {"energy": 260.2, "fiber": 2.5})
        self.assertEqual([r["key"] for r in rows], ["energy", "fiber"])
        self.assertEqual([r["percent"] for r in rows], [10.0, 10.0])

    def test_rows_without_amounts_have_no_share(self):
        norms = [{"key": "protein", "name": "Белки", "unit": "г", "value": 83}]
        row = build_norm_rows(norms)[0]
        self.assertIsNone(row["amount"])
        self.assertIsNone(row["percent"])

    def test_amounts_compute_energy_only_when_all_macros_known(self):
        self.assertEqual(amounts_from_macros(10, 5, 20, 2)["energy"], 165)
        self.assertIsNone(amounts_from_macros(10, None, 20, 2)["energy"])
        self.assertEqual(amounts_from_macros(10, 5, 20, 2, energy=99)["energy"], 99)

    def test_info_text_states_method_and_disclaimer(self):
        text = " ".join(NORMS_INFO["paragraphs"]) + NORMS_INFO["disclaimer"]
        for expected in ("МР 2.3.1.0253-21", "24 групп", "усреднённая", "пол"):
            self.assertIn(expected, text)


class SeededValuesTests(unittest.TestCase):
    def test_document_tables_have_24_adult_groups(self):
        self.assertEqual(len(MEN + WOMEN), 24)

    def test_seeded_norms_equal_rounded_average_of_document_groups(self):
        migration = load_migration()
        seeded = {n["key"]: n["value"] for n in migration.NORMS}
        rows = MEN + WOMEN
        for index, key in enumerate(("energy", "protein", "fat", "carbs")):
            average = sum(row[index] for row in rows) / len(rows)
            self.assertEqual(seeded[key], float(round(average)), key)
        self.assertEqual(seeded["fiber"], 25.0)

    def test_every_norm_key_is_seeded_with_the_document_source(self):
        migration = load_migration()
        self.assertEqual([n["key"] for n in migration.NORMS], list(NORM_ORDER))
        self.assertIn("МР 2.3.1.0253-21", migration.MR_SOURCE["title"])
        self.assertEqual(migration.MR_SOURCE["year"], 2021)
        for norm in migration.NORMS:
            self.assertTrue(norm["basis"])
            self.assertTrue(norm["unit"])


class FakeNormsRepository:
    def __init__(self, norms=(), registry=(), references=(), macros=None):
        self._norms = list(norms)
        self._registry = list(registry)
        self._references = list(references)
        self._macros = macros

    async def registry_sources(self):
        return self._registry

    async def reference_sources(self):
        return self._references

    async def norms(self):
        return self._norms

    async def product_macros(self, product_id):
        return self._macros


class ServiceTests(unittest.IsolatedAsyncioTestCase):
    def test_sources_registry_merges_reference_documents(self):
        sources = [
            {
                "id": uuid4(),
                "kind": "document",
                "title": "МР",
                "authors": "Роспотребнадзор",
                "year": 2021,
                "location": None,
                "url": "https://example.org/mr",
                "pdf_filename": None,
                "used_for": "Нормы",
            }
        ]
        shared = {
            "source_title": "FAO paper",
            "source_authors": "FAO; WHO",
            "source_year": 1991,
            "source_location": "т. 7",
            "source_url": "https://example.org/fao",
            "source_pdf_filename": None,
        }
        references = [
            {
                "name": "ФАО/ВОЗ 1973",
                "source_title": "Young",
                "source_authors": "V. Young. The Journal of Nutrition",
                "source_year": 1991,
                "source_location": "т. 1",
                "source_url": "https://example.org/young",
                "source_pdf_filename": None,
            },
            {"name": "ФАО/ВОЗ 1985", **shared},
            {"name": "ФАО/ВОЗ 1991", **shared},
        ]
        result = merge_sources(sources, references, lambda name: None)
        self.assertEqual(len(result), 3)
        by_title = {s["title"]: s for s in result}
        self.assertEqual(by_title["Young"]["kind"], "article")
        self.assertEqual(by_title["FAO paper"]["kind"], "document")
        self.assertEqual(
            by_title["FAO paper"]["used_for"],
            "Эталонный белок: ФАО/ВОЗ 1985, ФАО/ВОЗ 1991",
        )
        self.assertEqual(len({s["id"] for s in result}), 3)

    async def test_payload_returns_only_used_sources_and_info(self):
        source_id = uuid4()
        norms = [
            {
                "key": "protein",
                "name": "Белки",
                "unit": "г",
                "value": 83.0,
                "source_id": str(source_id),
                "basis": "b",
            }
        ]

        def registry_row(sid, title):
            return {
                "id": sid,
                "kind": "document",
                "title": title,
                "authors": None,
                "year": None,
                "location": None,
                "url": None,
                "pdf_filename": None,
                "used_for": None,
            }

        service = NormsService(
            FakeNormsRepository(
                norms=norms,
                registry=[
                    registry_row(source_id, "МР"),
                    registry_row(uuid4(), "Не используется"),
                ],
            )
        )
        payload = await service.payload(lambda name: None, {"protein": 41.5})
        self.assertEqual(payload["norms"][0]["percent"], 50.0)
        self.assertEqual([s["title"] for s in payload["sources"]], ["МР"])
        self.assertEqual(payload["info"], NORMS_INFO)

    async def test_product_macros_none_for_missing_product(self):
        db = Mock(scalar=AsyncMock(return_value=None))
        self.assertIsNone(await SqlNormsRepository(db).product_macros(uuid4()))

    async def test_product_macros_reads_chemical_composition(self):
        rows = [
            {"nutrient": "Массовая доля белка", "quantity": 10.0},
            {"nutrient": "Массовая доля жира", "quantity": 5.0},
            {"nutrient": "Углеводы", "quantity": 20.0},
        ]
        db = Mock(
            scalar=AsyncMock(return_value=1),
            execute=AsyncMock(return_value=FakeResult(rows)),
        )
        macros = await SqlNormsRepository(db).product_macros(uuid4())
        self.assertEqual(macros["Углеводы"], 20.0)

    async def test_product_payload_computes_energy_and_skips_missing_fiber(self):
        norm = {
            "key": "energy",
            "name": "Энергия",
            "unit": "ккал",
            "value": 2000.0,
            "source_id": None,
            "basis": "b",
        }
        macros = {
            "Массовая доля белка": 10.0,
            "Массовая доля жира": 5.0,
            "Углеводы": 20.0,
        }
        service = NormsService(FakeNormsRepository(norms=[norm], macros=macros))
        payload = await service.product_payload(uuid4(), lambda name: None)
        self.assertEqual(payload["norms"][0]["amount"], 165.0)

    async def test_product_payload_missing_product_is_not_found(self):
        service = NormsService(FakeNormsRepository(macros=None))
        with self.assertRaises(NotFoundError) as caught:
            await service.product_payload(uuid4(), lambda name: None)
        self.assertEqual(caught.exception.status_code, 404)


async def unused_db():
    raise AssertionError("Route tests must not connect to a database")


class RouteTests(unittest.TestCase):
    def load_norms_api(self):
        session_stub = ModuleType("core.db.session")
        session_stub.get_db = unused_db
        with patch.dict(sys.modules, {"core.db.session": session_stub}):
            import importlib

            module = importlib.import_module("features.norms.api.router")
            models = importlib.import_module("core.db.models")
        return module, models

    def test_routes_are_public_and_documented(self):
        norms, _models = self.load_norms_api()
        app = FastAPI()
        app.include_router(norms.router)
        paths = app.openapi()["paths"]
        for path in (
            "/api/v1/sources",
            "/api/v1/daily-norms",
            "/api/v1/products/{id}/daily-norms",
        ):
            operation = paths[path]["get"]
            self.assertNotIn("security", operation, path)


if __name__ == "__main__":
    unittest.main()
