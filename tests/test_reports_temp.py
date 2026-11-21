"""TEMP: reports_temp — отчёты на подменных запросах (без БД) и рендер PDF."""

import asyncio
import unittest
from datetime import UTC, datetime

from core.errors import BadRequestError, NotFoundError
from features.reports_temp.app import (
    MAX_LIST_ROWS,
    ListCriteria,
    RankingCriteria,
    ReportService,
)
from features.reports_temp.infra.pdf import render_pdf

NOW = datetime(2026, 11, 12, 10, 30, tzinfo=UTC)


class FakeQueries:
    def __init__(self, products=(), ranking=(), nutrients=(), unit="мг/100г"):
        self._products = list(products)
        self._ranking = list(ranking)
        self._nutrients = list(nutrients)
        self._unit = unit
        self.limits = []

    async def products(self, criteria, limit):
        self.limits.append(limit)
        return self._products[:limit]

    async def lookup_products(self, name, limit):
        return [{"id": "p1", "name": name, "category": "К", "region": "КР"}][:limit]

    async def nutrient_unit(self, name):
        return self._unit if name == "Лизин" else None

    async def ranking(self, criteria):
        return self._ranking[: criteria.top]

    async def product(self, product_id):
        if product_id != "p1":
            return None
        return {
            "id": "p1",
            "name": "Молоко сухое",
            "category": "Молочные",
            "subcategory": None,
            "region": "КР",
        }

    async def product_nutrients(self, product_id):
        return list(self._nutrients)

    async def options(self):
        return {}


def product(i, protein=10.0, fat=5.0, carb=2.0):
    return {
        "id": str(i),
        "name": f"Сырьё {i}",
        "region": "КР",
        "protein": protein,
        "fat": fat,
        "carb": carb,
    }


def run(coro):
    return asyncio.run(coro)


class ReportServiceTest(unittest.TestCase):
    def test_kcal_uses_calculator_formula_and_dash_when_incomplete(self):
        queries = FakeQueries(products=[product(1), product(2, carb=None)])
        doc = run(ReportService(queries).products_report(ListCriteria(), "Иван", NOW))
        rows = doc.sections[0].table.rows
        self.assertEqual(rows[0][-1], "93")  # 4*10 + 9*5 + 4*2
        self.assertEqual(rows[1][-1], "—")

    def test_list_truncated_over_limit(self):
        queries = FakeQueries(products=[product(i) for i in range(MAX_LIST_ROWS + 5)])
        doc = run(ReportService(queries).products_report(ListCriteria(), "Иван", NOW))
        self.assertEqual(len(doc.sections[0].table.rows), MAX_LIST_ROWS)
        self.assertTrue(any("первые" in n for n in doc.notes))

    def test_empty_list_has_message(self):
        doc = run(
            ReportService(FakeQueries()).products_report(ListCriteria(), "И", NOW)
        )
        self.assertIn("Нет данных", doc.empty_message)
        self.assertEqual(doc.sections, [])

    def test_lookup_ignores_blank_query(self):
        service = ReportService(FakeQueries())
        self.assertEqual(run(service.lookup("   ")), [])
        self.assertEqual(run(service.lookup(" мол "))[0]["name"], "мол")

    def test_ranking_validation(self):
        service = ReportService(FakeQueries())
        with self.assertRaises(BadRequestError):
            run(service.ranking_report(RankingCriteria("Нет такого"), "И", NOW))
        with self.assertRaises(BadRequestError):
            run(service.ranking_report(RankingCriteria("Лизин", top=101), "И", NOW))

    def test_ranking_rows_numbered(self):
        rows = [
            {
                "id": "1",
                "name": "А",
                "category": "К",
                "region": "КР",
                "quantity": 9.5,
                "error_rate": None,
            },
            {
                "id": "2",
                "name": "Б",
                "category": "К",
                "region": "КР",
                "quantity": 7.0,
                "error_rate": 0.1,
            },
        ]
        doc = run(
            ReportService(FakeQueries(ranking=rows)).ranking_report(
                RankingCriteria("Лизин", top=2), "И", NOW
            )
        )
        table = doc.sections[0].table
        self.assertEqual([r[0] for r in table.rows], ["1", "2"])
        self.assertEqual(table.rows[0][4], "9,5")
        self.assertEqual(table.rows[0][5], "—")

    def test_card_groups_in_fixed_order_and_not_found(self):
        nutrients = [
            {
                "type": "Минеральный состав",
                "name": "Fe",
                "unit": "мг/100г",
                "quantity": 1.0,
                "error_rate": None,
            },
            {
                "type": "Химический состав",
                "name": "Зольность",
                "unit": "%/100г",
                "quantity": 2.0,
                "error_rate": 0.1,
            },
        ]
        service = ReportService(FakeQueries(nutrients=nutrients))
        doc = run(service.card_report("p1", "И", NOW))
        self.assertEqual(
            [s.title for s in doc.sections], ["Химический состав", "Минеральный состав"]
        )
        with self.assertRaises(NotFoundError):
            run(service.card_report("missing", "И", NOW))


class PdfRenderTest(unittest.TestCase):
    def test_renders_valid_pdf_with_cyrillic_and_many_pages(self):
        queries = FakeQueries(products=[product(i) for i in range(300)])
        doc = run(
            ReportService(queries).products_report(
                ListCriteria(name="Мо"), "Иван Иванов", NOW
            )
        )
        data = render_pdf(doc)
        self.assertTrue(data.startswith(b"%PDF"))
        self.assertGreater(
            data.count(b"/Type /Page\n") + data.count(b"/Type /Page "), 2
        )

    def test_renders_empty_report(self):
        doc = run(
            ReportService(FakeQueries()).products_report(ListCriteria(), "И", NOW)
        )
        self.assertTrue(render_pdf(doc).startswith(b"%PDF"))


if __name__ == "__main__":
    unittest.main()
