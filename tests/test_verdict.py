"""Protein verdict checks: the conclusion depends only on the chosen reference."""

import inspect
import json
import unittest
from pathlib import Path

from domain.calculator import formulas
from domain.calculator.formulas import NAK_GROUPS, compute_report
from domain.calculator.optimizer import CandidateItem, _build_items


def control():
    data = json.loads(
        (Path(__file__).parent / "fixtures" / "control_recipe.json").read_text()
    )
    candidates = [CandidateItem(**item) for item in data["candidates"]]
    return candidates, data["reference"], data["baseline_amounts"]


def known_items():
    """Рецептура контроля без белоксодержащих ингредиентов без данных по НАК."""
    candidates, _, amounts = control()
    return [
        it
        for it in _build_items(candidates, amounts)
        if it.get("amino") or it["chem"].get("Массовая доля белка", 0.0) <= 0
    ]


def verdict_for(reference, *, complete_data=False):
    candidates, _, amounts = control()
    items = known_items() if complete_data else _build_items(candidates, amounts)
    return compute_report(items, reference)["verdict"]


def scaled(reference, factor, name):
    return {
        **reference,
        "name": name,
        "values": {k: v * factor for k, v in reference["values"].items()},
    }


class VerdictByReferenceChecks(unittest.TestCase):
    def test_control_recipe_is_incomplete_with_listed_deficits(self):
        _, reference, _ = control()
        verdict = verdict_for(reference)
        self.assertEqual(verdict["level"], "incomplete")
        self.assertEqual(
            verdict["headline"], "Белок неполноценный по эталону ФАО/ВОЗ 1973"
        )
        self.assertEqual(
            [d["name"] for d in verdict["deficits"]],
            ["ВАЛ", "ИЗО", "ТРЕ", "ЛЕЙ", "МЕТ+ЦИС"],
        )
        valine = verdict["deficits"][0]
        self.assertEqual(valine["score"], 73.3)
        self.assertEqual(valine["reference"], 5.0)
        self.assertAlmostEqual(
            valine["deficit"], valine["reference"] - valine["m_j"], places=2
        )

    def test_complete_when_every_score_reaches_reference(self):
        _, reference, _ = control()
        verdict = verdict_for(
            scaled(reference, 0.5, "Мягкий эталон"), complete_data=True
        )
        self.assertEqual(verdict["level"], "complete")
        self.assertEqual(
            verdict["headline"], "Белок полноценный по эталону Мягкий эталон"
        )
        self.assertEqual(verdict["deficits"], [])

    def test_changing_reference_changes_scores_and_text(self):
        _, reference, _ = control()
        strict = verdict_for(scaled(reference, 1.2, "Строгий эталон"))
        base = verdict_for(reference)
        self.assertNotEqual(strict["headline"], base["headline"])
        self.assertGreater(len(strict["deficits"]), len(base["deficits"]))
        self.assertEqual(strict["reference"]["name"], "Строгий эталон")
        self.assertIn("«Строгий эталон»", strict["points"][0])

    def _items_with_missing_amino(self):
        _, reference, _ = control()
        items = known_items()
        # Добавляем белковый ингредиент без данных по НАК.
        extra = {
            **items[0],
            "name": "Без аминокислот",
            "amino": {},
            "amount_g": 20.0,
        }
        return items, extra, reference

    def test_missing_amino_data_is_reported_as_limitation(self):
        items, extra, reference = self._items_with_missing_amino()
        verdict = compute_report([*items, extra], reference)["verdict"]
        self.assertEqual(len(verdict["limitations"]), 1)
        self.assertIn("Без аминокислот", verdict["limitations"][0])
        self.assertIn("не учтены", verdict["limitations"][0])
        self.assertIn(verdict["limitations"][0], verdict["points"])

    def test_complete_with_missing_data_is_unconfirmed(self):
        items, extra, reference = self._items_with_missing_amino()
        soft = scaled(reference, 0.5, "Мягкий эталон")
        verdict = compute_report([*items, extra], soft)["verdict"]
        self.assertEqual(verdict["level"], "unconfirmed")
        self.assertNotIn("полноценный по эталону", verdict["headline"].split(":")[0])
        self.assertIn("не подтверждена", verdict["headline"])

    def test_full_data_has_no_limitations_and_has_explanation(self):
        _, reference, _ = control()
        verdict = verdict_for(reference, complete_data=True)
        self.assertEqual(verdict["limitations"], [])
        self.assertEqual(
            [row["code"] for row in verdict["explanation"]], ["КРАС", "БЦ", "U", "G"]
        )
        self.assertIn("100 %", verdict["criterion"])
        self.assertIn("source", verdict["reference"])

    def test_boundary_score_exactly_100_is_not_a_deficit(self):
        _, reference, _ = control()
        items = known_items()
        raw = compute_report(items, reference, rounded=False)
        exact = {
            **reference,
            "values": {r["name"]: r["m_j"] for r in raw["amino_acids"]},
        }
        verdict = compute_report(items, exact, rounded=False)["verdict"]
        self.assertEqual(verdict["level"], "complete")

    def test_contract_has_reference_note_and_numeric_indicators(self):
        _, reference, _ = control()
        verdict = verdict_for(reference)
        for key in (
            "level",
            "headline",
            "points",
            "reference",
            "deficits",
            "experimental_note",
        ):
            self.assertIn(key, verdict)
        self.assertEqual(
            verdict["reference"],
            {"name": "ФАО/ВОЗ 1973", "year": 1973, "source": None},
        )
        self.assertTrue(
            verdict["experimental_note"].startswith("Экспериментальная функция")
        )
        text = " ".join(verdict["points"])
        self.assertIn("КРАС = 21,7 %", text)
        self.assertIn("БЦ = 78,3 %", text)
        self.assertIn("U = 0,79", text)
        self.assertIn("Усвояемость белка не учитывается", text)

    def test_no_amino_data_gives_no_verdict(self):
        report = compute_report(
            [
                {
                    "product_id": "1",
                    "name": "Вода",
                    "amount_g": 100,
                    "chem": {},
                    "amino": {},
                }
            ],
            {"id": "r", "name": "X", "values": {g: 1.0 for g, _ in NAK_GROUPS}},
        )
        self.assertIsNone(report["verdict"])

    def test_conditional_thresholds_and_levels_are_gone(self):
        source = inspect.getsource(formulas)
        for forbidden in (
            "c_min_val >= 95",
            "c_min_val >= 70",
            "kras < 10",
            "kras < 25",
        ):
            self.assertNotIn(forbidden, source)
        for level in ("good", "moderate", "poor"):
            self.assertNotIn(f'"{level}"', source)


if __name__ == "__main__":
    unittest.main()
