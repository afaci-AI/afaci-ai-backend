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


def verdict_for(reference):
    candidates, _, amounts = control()
    return compute_report(_build_items(candidates, amounts), reference)["verdict"]


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
        verdict = verdict_for(scaled(reference, 0.5, "Мягкий эталон"))
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

    def test_boundary_score_exactly_100_is_not_a_deficit(self):
        candidates, reference, amounts = control()
        items = _build_items(candidates, amounts)
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
        self.assertEqual(verdict["reference"], {"name": "ФАО/ВОЗ 1973", "year": 1973})
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
