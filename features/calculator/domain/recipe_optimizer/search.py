"""Выбор состава: решения ЛП, проверенные методикой.

Основной путь — одна задача линейного программирования на режим (цена или
ценность). Её решение проверяется пересчётом `compute_report`: наружу не
выходит состав, показатели которого не подтверждены методикой. Если задача
недопустима, работает запасной вариант (`lp_fallback.py`) с прежним
лексикографическим порядком приоритетов. Чем режимы отличаются друг от
друга — в `modes.py`; здесь только общий порядок поиска.
"""

from __future__ import annotations

import numpy as np

from ..candidates import CandidateItem, build_items
from ..formulas import compute_report
from ..formulas.linear import LinearForms
from ..lp_model import fit_mass
from .errors import COMPARISON_TOLERANCE, METRICS, RecipeOptimizationError
from .lp_fallback import candidates_for, minimum_violation
from .modes import OptimizationMode
from .recipe import EvaluatedRecipe
from .validation import is_finite

SIGNS = np.array([1, 1, -1])  # БЦ и U — больше лучше, G — меньше лучше
# Сбой вычислений решателя не должен превращаться в непроверенный ответ:
# такие ошибки означают «решения нет», и дальше работает запасной вариант.
SOLVER_FAILURES = (ArithmeticError, RuntimeError, np.linalg.LinAlgError)


class RecipeSearch:
    """Решает задачу режима и выбирает состав среди проверенных вариантов."""

    def __init__(
        self,
        candidates: list[CandidateItem],
        reference: dict,
        mode: OptimizationMode,
        forms: LinearForms,
        bounds: tuple[np.ndarray, np.ndarray],
        prices: np.ndarray,
        base_quality: np.ndarray,
        base_cost: float,
        protein_min: float | None = None,
    ) -> None:
        self.candidates = candidates
        self.reference = reference
        self.mode = mode
        self.forms = forms
        self.lower, self.upper = bounds
        self.prices = prices
        self.base_quality = base_quality
        self.base_cost = base_cost
        self.protein_min = protein_min
        # No arbitrary weights: each violation is divided by its own baseline.
        self.scales = np.array([abs(v) if v != 0 else 1.0 for v in base_quality])
        self.records: list[EvaluatedRecipe] = []

    @property
    def original(self) -> dict:
        return dict(zip(METRICS, (float(v) for v in self.base_quality), strict=True))

    # ----------------------------------------------------------- оценка
    def evaluate(self, x) -> EvaluatedRecipe | None:
        """Пересчитать состав методикой; `None`, если он непригоден."""
        if not np.isfinite(x).all():
            return None
        amounts = fit_mass(x, self.lower, self.upper)
        if abs(float(amounts.sum()) - 100.0) > COMPARISON_TOLERANCE:
            return None
        try:
            quality = compute_report(
                build_items(self.candidates, amounts), self.reference, rounded=False
            )["quality_precise"]
        except (ArithmeticError, TypeError, ValueError):
            return None
        if not all(is_finite(quality.get(m)) for m in (*METRICS, "kras")):
            return None
        actual = np.array([quality[m] for m in METRICS])
        differences = (self.base_quality - actual) * SIGNS
        result = EvaluatedRecipe(
            amounts,
            quality,
            float(np.dot(self.prices, amounts)),
            np.maximum(differences, 0) / self.scales,
        )
        self.records.append(result)
        return result

    def entries(self) -> list[EvaluatedRecipe]:
        return list(self.records)

    def rank(self, entry: EvaluatedRecipe) -> float:
        return self.mode.rank(entry)

    def margins(self, entry: EvaluatedRecipe) -> np.ndarray:
        actual = np.array([entry.quality[m] for m in METRICS])
        return (actual - self.base_quality) * SIGNS

    def achieved(self, entry: EvaluatedRecipe) -> bool:
        tol = COMPARISON_TOLERANCE
        margins = self.margins(entry)
        improvement = self.mode.improvement(
            entry, base_cost=self.base_cost, margins=margins
        )
        return bool(np.all(margins >= -tol) and improvement > tol)

    # ------------------------------------------------------------ поиск
    def _main(self, baseline: np.ndarray):
        """Решение задачи режима: минимум цены либо максимум ценности."""
        try:
            return self.mode.solve(
                self.forms,
                lower=self.lower,
                upper=self.upper,
                prices=self.prices,
                original=self.original,
                baseline=baseline,
                tolerance=COMPARISON_TOLERANCE,
            )
        except SOLVER_FAILURES:
            return None

    def _fallback(self) -> None:
        """Составы с наименьшим нарушением порогов, когда цель недостижима."""
        try:
            self._collect()
        except SOLVER_FAILURES:
            return

    def _collect(self) -> None:
        violation = minimum_violation(
            self.forms,
            lower=self.lower,
            upper=self.upper,
            prices=self.prices,
            original=self.original,
            scales=self.scales,
            protein_min=self.protein_min,
        )
        if violation is None:
            return
        for amounts in candidates_for(
            self.forms,
            lower=self.lower,
            upper=self.upper,
            prices=self.prices,
            original=self.original,
            scales=self.scales,
            protein_min=self.protein_min,
            violation=violation,
        ):
            self.evaluate(amounts)

    def run(self, baseline: np.ndarray) -> EvaluatedRecipe:
        """Состав режима: решение ЛП, при недопустимости — запасной вариант."""
        amounts = self._main(baseline)
        if amounts is not None:
            entry = self.evaluate(amounts)
            if entry is not None and np.all(
                self.margins(entry) >= -COMPARISON_TOLERANCE
            ):
                return entry
        self._fallback()
        return self._select([e for e in self.entries() if self.achieved(e)])

    def _select(self, found: list[EvaluatedRecipe]) -> EvaluatedRecipe:
        tol = COMPARISON_TOLERANCE
        if found:
            return min(found, key=self.rank)
        available = self.entries()
        if not available:
            raise RecipeOptimizationError(
                "Не удалось получить и проверить рассчитываемый состав в заданных диапазонах.",
                "optimization_calculation_failed",
            )
        best_max = min(float(e.violations.max()) for e in available)
        available = [e for e in available if e.violations.max() <= best_max + tol]
        best_sum = min(float(e.violations.sum()) for e in available)
        available = [e for e in available if e.violations.sum() <= best_sum + tol]
        return min(available, key=self.rank)
