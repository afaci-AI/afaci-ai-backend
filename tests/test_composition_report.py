"""Сценарий `/compute`: отчёт калькулятора дополняется суточными нормами."""

import unittest
from uuid import uuid4

from features.calculator.api.deps import _DailyNormsAdapter
from features.calculator.app import CompositionReport
from features.norms.app import NormsService
from features.norms.domain.records import DailyNorm, RegistrySource


class FakeCalculator:
    def __init__(self, report: dict) -> None:
        self.report = report
        self.calls: list[tuple] = []

    async def compute(self, reference_protein_id, items):
        self.calls.append((reference_protein_id, items))
        return dict(self.report)


class FakeDailyNorms:
    def __init__(self) -> None:
        self.received: dict | None = None

    async def for_recipe(self, *, macro, energy_kcal, micro, other):
        self.received = {
            "macro": macro,
            "energy_kcal": energy_kcal,
            "micro": micro,
            "other": other,
        }
        return {"macro": ["нормы"]}


class FakeNormsRepository:
    def __init__(self, registry=(), norms=None):
        self._registry = list(registry)
        self._norms = norms or [
            DailyNorm(key="protein", name="Белки", unit="г", value=80.0, basis="b")
        ]

    async def registry_sources(self):
        return self._registry

    async def reference_sources(self):
        return []

    async def norms(self):
        return self._norms


REPORT = {
    "macro": {"protein": 20.0, "fat": 10.0, "carb": 5.0, "fiber": 1.0},
    "energy_kcal": 190.0,
    "micro": [{"name": "Кальций"}],
    "other": [],
}


class CompositionReportTests(unittest.IsolatedAsyncioTestCase):
    async def test_report_gets_daily_norms_from_its_own_macro_and_energy(self):
        norms = FakeDailyNorms()
        report = CompositionReport(FakeCalculator(REPORT), norms)

        result = await report.compute(
            uuid4(), [{"product_id": uuid4(), "amount_g": 100}]
        )

        self.assertEqual(result["daily_norms"], {"macro": ["нормы"]})
        self.assertEqual(norms.received["macro"], REPORT["macro"])
        self.assertEqual(norms.received["energy_kcal"], 190.0)
        self.assertEqual(norms.received["micro"], REPORT["micro"])

    async def test_calculator_receives_request_unchanged(self):
        calculator = FakeCalculator(REPORT)
        reference_id = uuid4()
        items = [{"product_id": uuid4(), "amount_g": 100}]

        await CompositionReport(calculator, FakeDailyNorms()).compute(
            reference_id, items
        )

        self.assertEqual(calculator.calls, [(reference_id, items)])


class RecipePayloadTests(unittest.IsolatedAsyncioTestCase):
    async def test_share_of_norm_uses_recipe_macro_per_100_g(self):
        service = NormsService(FakeNormsRepository())

        payload = await service.recipe_payload(REPORT["macro"], 190.0, [], [])

        self.assertEqual(payload.macro[0].percent, 25.0)


class DailyNormsAdapterTests(unittest.IsolatedAsyncioTestCase):
    """Калькулятор получает от норм готовый ответ: записи состава и ссылки на PDF."""

    async def test_report_rows_become_entries_and_sources_get_pdf_links(self):
        source = RegistrySource(
            id="mr", kind="document", title="МР", pdf_filename="mr.pdf"
        )
        norms = [
            DailyNorm(
                key="protein", name="Белки", unit="г", value=80.0, source_id="mr"
            ),
            DailyNorm(key="Ca", unit="мг", value=1000.0, source_id="mr"),
        ]
        adapter = _DailyNormsAdapter(
            NormsService(FakeNormsRepository(registry=[source], norms=norms)),
            lambda filename: f"https://docs/{filename}" if filename else None,
        )

        payload = await adapter.for_recipe(
            macro=REPORT["macro"],
            energy_kcal=190.0,
            micro=[{"name": "Ca", "unit": "мг/100г", "amount": 100.0, "partial": True}],
            other=[],
        )

        (calcium,) = payload["micro"]
        self.assertEqual(calcium["percent"], 10.0)
        self.assertTrue(calcium["partial"])
        (shown,) = payload["sources"]
        self.assertEqual(shown["pdf_url"], "https://docs/mr.pdf")
        self.assertNotIn("pdf_filename", shown)


if __name__ == "__main__":
    unittest.main()
