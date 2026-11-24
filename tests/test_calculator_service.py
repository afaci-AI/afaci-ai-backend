"""Расчёт через сервис и типизированные порты совпадает с эталоном формул."""

import json
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock
from uuid import UUID, uuid4

from core.errors import NotFoundError
from features.calculator.app import RecipeCalculator
from features.calculator.domain import (
    CandidateItem,
    ProductNutrients,
    ReferenceProtein,
    build_items,
    compute_report,
)
from features.calculator.infra.sql_reader import (
    AMINO_TYPE,
    CHEM_TYPE,
    SqlCalculatorData,
)

FIXTURES = Path(__file__).parent / "fixtures"


def control():
    data = json.loads((FIXTURES / "control_recipe.json").read_text(encoding="utf-8"))
    return data["candidates"], data["reference"], data["baseline_amounts"]


class FakeData:
    def __init__(self, products, reference):
        self.products = products
        self.reference = reference

    async def get_reference(self, reference_id):
        return self.reference

    async def load_products(self, ids):
        wanted = {str(i) for i in ids}
        return {pid: p for pid, p in self.products.items() if pid in wanted}


class CalculatorThroughPorts(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        candidates, reference, baseline = control()
        self.raw_reference = reference
        self.baseline = baseline
        self.candidates = [CandidateItem(**c) for c in candidates]
        # Идентификаторы в фикстуре — не UUID; сервис переводит их в UUID.
        self.ids = [str(uuid4()) for _ in candidates]
        products = {
            pid: ProductNutrients(
                product_id=pid,
                name=c["name"],
                region=None,
                subcategory=None,
                chem=c["chem"],
                amino=c["amino"],
            )
            for pid, c in zip(self.ids, candidates, strict=True)
        }
        ref = ReferenceProtein(
            id=reference["id"],
            name=reference["name"],
            year=reference["year"],
            description=None,
            source=None,
            values=reference["values"],
        )
        self.data = FakeData(products, ref)
        self.calculator = RecipeCalculator(self.data, self.data)

    async def test_compute_matches_formulas_on_plain_dicts(self):
        items = [
            {"product_id": UUID(pid), "amount_g": amount}
            for pid, amount in zip(self.ids, self.baseline, strict=True)
        ]
        result = await self.calculator.compute(uuid4(), items)

        renamed = [
            CandidateItem(**{**vars(c), "product_id": pid})
            for c, pid in zip(self.candidates, self.ids, strict=True)
        ]
        expected = compute_report(
            build_items(renamed, self.baseline),
            {**self.raw_reference, "description": None, "source": None},
        )
        self.assertEqual(result, expected)

    async def test_missing_product_is_reported(self):
        items = [{"product_id": uuid4(), "amount_g": 100.0}]
        with self.assertRaises(NotFoundError):
            await self.calculator.compute(uuid4(), items)

    async def test_missing_reference_is_reported(self):
        self.data.reference = None
        items = [{"product_id": UUID(self.ids[0]), "amount_g": 100.0}]
        with self.assertRaises(NotFoundError):
            await self.calculator.compute(uuid4(), items)


def nutrient_row(pid, nutrient, ntype, quantity, nclass=None, unit=None):
    return {
        "product_id": pid,
        "name": "Говядина",
        "region": "Кыргызстан",
        "subcategory": None,
        "nutrient": nutrient,
        "ntype": ntype,
        "quantity": quantity,
        "nclass": nclass,
        "unit": unit,
    }


class ProductNutrientsFromSql(unittest.IsolatedAsyncioTestCase):
    async def test_rows_are_grouped_by_composition_type_and_class(self):
        pid, empty = uuid4(), uuid4()
        result = Mock()
        result.mappings.return_value.all.return_value = [
            nutrient_row(pid, "Белок", CHEM_TYPE, 18.6),
            nutrient_row(pid, "ЛИЗ", AMINO_TYPE, 8.1),
            nutrient_row(pid, "Железо", "Минеральный состав", 2.6, "micro", "мг"),
            nutrient_row(empty, None, None, None),
        ]
        db = Mock()
        db.execute = AsyncMock(return_value=result)

        products = await SqlCalculatorData(db).load_products([pid, empty])

        beef = products[str(pid)]
        self.assertEqual(beef.chem, {"Белок": 18.6})
        self.assertEqual(beef.amino, {"ЛИЗ": 8.1})
        self.assertEqual(beef.micro, {"Железо": 2.6})
        self.assertEqual(beef.units, {"Железо": "мг"})
        self.assertEqual(beef.other, {})
        self.assertEqual(products[str(empty)].chem, {})


if __name__ == "__main__":
    unittest.main()
