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
    recipe_nutrition,
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

    async def user_recipes(self, user_id):
        return [{"id": "r1", "name": "Котлеты"}] if user_id == "u1" else []

    async def saved_recipe(self, recipe_id, user_id):
        if (recipe_id, user_id) != ("r1", "u1"):
            return None
        return {"id": "r1", "name": "Котлеты", "reference_id": "ref"}

    async def recipe_items(self, recipe_id):
        return [dict(it) for it in RECIPE]

    async def reference(self, reference_id):
        return dict(REFERENCE)

    async def options(self):
        return {}


PROTEIN, FAT, CARB = "Массовая доля белка", "Массовая доля жира", "Углеводы"
REFERENCE = {"name": "ФАО/ВОЗ", "values": {"ЛИЗ": 5.5, "ТРИ": 1.0}}
RECIPE = [
    {
        "name": "Говядина",
        "amount_g": 60.0,
        "chem": {PROTEIN: 20.0, FAT: 10.0, CARB: 0.0},
        # 1600 мг лизина на 20 % белка: 8 г/100 г белка; триптофан 2 г/100 г белка.
        "amino": {"Лизин": 1600.0, "Триптофан": 400.0},
    },
    {
        "name": "Хлеб",
        "amount_g": 40.0,
        "chem": {PROTEIN: 8.0, FAT: 1.0, CARB: 50.0},
        "amino": {"Лизин": 160.0, "Триптофан": 80.0},
    },
    {"name": "Соль", "amount_g": 0.0, "chem": {}, "amino": {}},
]


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


class RecipeNutritionTest(unittest.TestCase):
    def test_macro_energy_and_limiting_amino_acid(self):
        result = recipe_nutrition(RECIPE, REFERENCE)
        self.assertAlmostEqual(result.mass_g, 100.0)
        self.assertAlmostEqual(result.protein, 15.2)  # (20·60 + 8·40) / 100
        self.assertAlmostEqual(result.fat, 6.4)
        self.assertAlmostEqual(result.carb, 20.0)
        self.assertAlmostEqual(result.energy_kcal, 4 * 15.2 + 9 * 6.4 + 4 * 20.0)
        scores = {s.name: s.score for s in result.scores}
        # Mⱼ лизина = (1200·8 + 320·2) / 1520 = 6,7368 г/100 г белка.
        self.assertAlmostEqual(scores["ЛИЗ"], 6.736842 / 5.5 * 100, places=3)
        self.assertIsNone(scores["ИЗО"])  # в эталоне нет значения
        self.assertEqual(result.limiting.name, "ЛИЗ")

    def test_empty_recipe_rejected(self):
        with self.assertRaises(BadRequestError):
            recipe_nutrition([{"name": "Соль", "amount_g": 0.0}], REFERENCE)

    def test_without_amino_data_no_limiting(self):
        items = [{**RECIPE[1], "amino": {}}]
        result = recipe_nutrition(items, REFERENCE)
        self.assertEqual(result.scores, [])
        self.assertIsNone(result.limiting)


class NutritionReportTest(unittest.TestCase):
    def test_report_has_composition_value_and_score(self):
        service = ReportService(FakeQueries())
        doc = run(service.nutrition_report("r1", "u1", "Иван", NOW))
        titles = [s.title for s in doc.sections]
        self.assertEqual(
            titles,
            ["Состав рецептуры", "Пищевая ценность на 100 г", "Аминокислотный скор"],
        )
        self.assertIn(["Белок", "15,2", "г"], doc.sections[1].table.rows)
        self.assertTrue(any("Лимитирующая аминокислота: ЛИЗ" in n for n in doc.notes))
        self.assertTrue(render_pdf(doc).startswith(b"%PDF"))

    def test_foreign_or_missing_recipe_not_found(self):
        service = ReportService(FakeQueries())
        with self.assertRaises(NotFoundError):
            run(service.nutrition_report("r1", "u2", "Иван", NOW))
        self.assertEqual(run(service.recipes("u2")), [])


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
