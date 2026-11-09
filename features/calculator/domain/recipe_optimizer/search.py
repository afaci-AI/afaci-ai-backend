"""Численный поиск состава: SLSQP из нескольких стартов и запасной вариант.

Fallback order is lexicographic: maximum relative quality violation, sum of
relative violations, then maximum BV (basic) or minimum price (cost).
SLSQP is a local numerical search, not a proof of global optimality.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.optimize import Bounds, minimize

from ..candidates import CandidateItem, build_items
from ..formulas import compute_report
from .errors import COMPARISON_TOLERANCE, METRICS, RecipeOptimizationError
from .simplex import project
from .validation import is_finite

SIGNS = np.array([1, 1, -1])  # БЦ и U — больше лучше, G — меньше лучше


@dataclass
class EvaluatedRecipe:
    amounts: np.ndarray
    quality: dict
    cost: float
    violations: np.ndarray


class RecipeSearch:
    """Оценивает составы (с кэшем) и ищет лучший относительно исходного."""

    def __init__(
        self,
        candidates: list[CandidateItem],
        reference: dict,
        mode: str,
        bounds: tuple[np.ndarray, np.ndarray],
        prices: np.ndarray,
        base_quality: np.ndarray,
        base_cost: float,
    ) -> None:
        self.candidates = candidates
        self.reference = reference
        self.mode = mode
        self.lower, self.upper = bounds
        self.prices = prices
        self.base_quality = base_quality
        self.base_cost = base_cost
        # No arbitrary weights: each violation is divided by its own baseline.
        self.scales = np.array([abs(v) if v != 0 else 1.0 for v in base_quality])
        self.records: dict[tuple, EvaluatedRecipe | None] = {}

    # ----------------------------------------------------------- оценка
    def evaluate(self, x) -> EvaluatedRecipe | None:
        tol = COMPARISON_TOLERANCE
        key = tuple(float(v) for v in x)
        if key in self.records:
            return self.records[key]
        self.records[key] = None
        if (
            not np.isfinite(x).all()
            or np.any(x < self.lower - tol)
            or np.any(x > self.upper + tol)
            or abs(float(np.sum(x)) - 100) > tol
        ):
            return None
        # Evaluate the exact composition that will be returned and saved.
        amounts = project(np.asarray(x), self.lower, self.upper)
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
        violation = np.maximum(differences, 0) / self.scales
        result = EvaluatedRecipe(
            amounts, quality, float(np.dot(self.prices, amounts)), violation
        )
        self.records[key] = result
        return result

    def entries(self) -> list[EvaluatedRecipe]:
        return [entry for entry in self.records.values() if entry is not None]

    def rank(self, entry: EvaluatedRecipe) -> float:
        return entry.cost if self.mode == "cost" else -entry.quality["bc"]

    def margins(self, entry: EvaluatedRecipe) -> np.ndarray:
        actual = np.array([entry.quality[m] for m in METRICS])
        return (actual - self.base_quality) * SIGNS

    def achieved(self, entry: EvaluatedRecipe) -> bool:
        tol = COMPARISON_TOLERANCE
        margins = self.margins(entry)
        improvement = (
            self.base_cost - entry.cost if self.mode == "cost" else float(margins.max())
        )
        return bool(np.all(margins >= -tol) and improvement > tol)

    # ------------------------------------------------------------ поиск
    def objective(self, x) -> float:
        entry = self.evaluate(x)
        return 1e12 if entry is None else self.rank(entry)

    def quality_margin(self, x) -> np.ndarray:
        entry = self.evaluate(x)
        return np.full(3, -1e12) if entry is None else self.margins(entry)

    def search(self, fun, start, extra) -> None:
        self.evaluate(start)
        try:
            result = minimize(
                fun,
                start,
                method="SLSQP",
                bounds=Bounds(self.lower, self.upper),
                constraints=[
                    {"type": "eq", "fun": lambda x: float(np.sum(x)) - 100},
                    *extra,
                ],
                options={"ftol": 1e-10, "maxiter": 250, "disp": False},
            )
            self.evaluate(result.x)
        except (ArithmeticError, ValueError, RuntimeError):
            pass

    def run(self, starts: list[np.ndarray]) -> EvaluatedRecipe:
        """Основной поиск, при неудаче — лексикографический запасной вариант."""
        for start in starts:
            self.search(
                self.objective, start, [{"type": "ineq", "fun": self.quality_margin}]
            )
        found = [entry for entry in self.entries() if self.achieved(entry)]
        if not found:
            self._fallback(starts)
            found = [entry for entry in self.entries() if self.achieved(entry)]
        return self._select(found)

    def _violation(self, kind: str):
        def value(x) -> float:
            entry = self.evaluate(x)
            if not entry:
                return 1e12
            return float(getattr(entry.violations, kind)())

        return value

    def _fallback(self, starts: list[np.ndarray]) -> None:
        """Lexicographic fallback, without mixing metric priorities into weights."""
        tol = COMPARISON_TOLERANCE
        maximum, total = self._violation("max"), self._violation("sum")
        for start in starts:
            self.search(maximum, start, [])
        if not self.entries():
            return
        best_max = min(float(e.violations.max()) for e in self.entries())
        max_constraint = {
            "type": "ineq",
            "fun": lambda x: best_max + tol - maximum(x),
        }
        stage_starts = sorted(self.entries(), key=lambda e: e.violations.max())[:3]
        for entry in stage_starts:
            self.search(total, entry.amounts, [max_constraint])
        permitted = [e for e in self.entries() if e.violations.max() <= best_max + tol]
        best_sum = min(float(e.violations.sum()) for e in permitted)
        total_constraint = {
            "type": "ineq",
            "fun": lambda x: best_sum + tol - total(x),
        }
        for entry in sorted(permitted, key=lambda e: e.violations.sum())[:3]:
            self.search(
                self.objective, entry.amounts, [max_constraint, total_constraint]
            )

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
