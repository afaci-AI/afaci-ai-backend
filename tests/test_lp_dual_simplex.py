"""Тесты модуля ЛП: учебные задачи, вырождение, зацикливание, тёплый старт."""

import unittest
from pathlib import Path

from libs.lp import INF, LpProblemError, LpStatus, make_problem, solve

PACKAGE = Path(__file__).resolve().parent.parent / "libs" / "lp"
FORBIDDEN_SOLVERS = ("scipy", "linprog", "highs", "pulp", "ortools", "cvxpy")


def klee_minty(size: int):
    """Задача Кли–Минти: 2^n вершин, оптимум 100^(n−1) при x_n = 100^(n−1)."""
    cost = [-(10.0 ** (size - 1 - index)) for index in range(size)]
    rows = []
    rhs = []
    for row in range(size):
        coefficients = [0.0] * size
        for column in range(row):
            coefficients[column] = 2.0 * 10.0 ** (row - column)
        coefficients[row] = 1.0
        rows.append(coefficients)
        rhs.append(100.0**row)
    bound = 100.0 ** (size - 1)
    return make_problem(
        cost, a_ub=rows, b_ub=rhs, lower=[0.0] * size, upper=[bound] * size
    )


class SmallProblems(unittest.TestCase):
    def test_minimum_at_vertex(self):
        problem = make_problem(
            [-1.0, -2.0],
            a_ub=[[1.0, 1.0], [1.0, 3.0]],
            b_ub=[4.0, 6.0],
            upper=[10.0, 10.0],
        )
        result = solve(problem)
        self.assertIs(result.status, LpStatus.OPTIMAL)
        self.assertAlmostEqual(result.objective, -5.0, places=9)
        self.assertAlmostEqual(result.x[0], 3.0, places=9)
        self.assertAlmostEqual(result.x[1], 1.0, places=9)
        self.assertLess(result.residual, 1e-9)

    def test_equality_rows(self):
        problem = make_problem(
            [2.0, 3.0, 1.0],
            a_eq=[[1.0, 1.0, 1.0], [1.0, -1.0, 0.0]],
            b_eq=[10.0, 2.0],
            upper=[10.0, 10.0, 10.0],
        )
        result = solve(problem)
        self.assertIs(result.status, LpStatus.OPTIMAL)
        self.assertAlmostEqual(sum(result.x), 10.0, places=9)
        self.assertAlmostEqual(result.x[0] - result.x[1], 2.0, places=9)
        self.assertAlmostEqual(result.objective, 12.0, places=9)

    def test_greater_rows_are_converted(self):
        problem = make_problem(
            [1.0, 1.0], a_lb=[[1.0, 2.0]], b_lb=[4.0], upper=[10.0, 10.0]
        )
        result = solve(problem)
        self.assertIs(result.status, LpStatus.OPTIMAL)
        self.assertAlmostEqual(result.objective, 2.0, places=9)

    def test_free_variables(self):
        problem = make_problem(
            [1.0, 1.0],
            a_lb=[[1.0, 1.0]],
            b_lb=[2.0],
            a_eq=[[1.0, -1.0]],
            b_eq=[0.0],
            lower=[-INF, -INF],
            upper=[INF, INF],
        )
        result = solve(problem)
        self.assertIs(result.status, LpStatus.OPTIMAL)
        self.assertAlmostEqual(result.x[0], 1.0, places=9)
        self.assertAlmostEqual(result.x[1], 1.0, places=9)

    def test_fixed_variable(self):
        problem = make_problem(
            [1.0, 1.0],
            a_ub=[[1.0, 1.0]],
            b_ub=[10.0],
            lower=[2.0, 0.0],
            upper=[2.0, 5.0],
        )
        result = solve(problem)
        self.assertIs(result.status, LpStatus.OPTIMAL)
        self.assertAlmostEqual(result.x[0], 2.0, places=9)
        self.assertAlmostEqual(result.objective, 2.0, places=9)


class HardProblems(unittest.TestCase):
    def test_beale_cycling_example(self):
        problem = make_problem(
            [-0.75, 150.0, -0.02, 6.0],
            a_ub=[
                [0.25, -60.0, -0.04, 9.0],
                [0.5, -90.0, -0.02, 3.0],
                [0.0, 0.0, 1.0, 0.0],
            ],
            b_ub=[0.0, 0.0, 1.0],
            upper=[10.0, 10.0, 10.0, 10.0],
        )
        result = solve(problem)
        self.assertIs(result.status, LpStatus.OPTIMAL)
        self.assertAlmostEqual(result.objective, -0.05, places=9)

    def test_klee_minty(self):
        for size in (3, 4, 5, 6):
            with self.subTest(size=size):
                result = solve(klee_minty(size))
                self.assertIs(result.status, LpStatus.OPTIMAL)
                expected = -(100.0 ** (size - 1))
                self.assertAlmostEqual(result.objective / expected, 1.0, places=6)

    def test_degenerate_rows(self):
        problem = make_problem(
            [-1.0, -1.0],
            a_ub=[[1.0, 1.0], [1.0, 2.0], [2.0, 1.0], [1.0, 0.0]],
            b_ub=[1.0, 2.0, 2.0, 1.0],
            upper=[1.0, 1.0],
        )
        result = solve(problem)
        self.assertIs(result.status, LpStatus.OPTIMAL)
        self.assertAlmostEqual(result.objective, -1.0, places=9)

    def test_infeasible_rows(self):
        problem = make_problem(
            [1.0, 1.0],
            a_ub=[[1.0, 1.0], [-1.0, -1.0]],
            b_ub=[1.0, -5.0],
            upper=[10.0, 10.0],
        )
        self.assertIs(solve(problem).status, LpStatus.INFEASIBLE)

    def test_infeasible_equality(self):
        problem = make_problem(
            [1.0], a_eq=[[1.0]], b_eq=[5.0], lower=[0.0], upper=[1.0]
        )
        self.assertIs(solve(problem).status, LpStatus.INFEASIBLE)

    def test_unbounded_problem(self):
        problem = make_problem([-1.0], lower=[0.0], upper=[INF])
        self.assertIs(solve(problem).status, LpStatus.UNBOUNDED)

    def test_iteration_limit(self):
        result = solve(klee_minty(6), max_iter=1)
        self.assertIs(result.status, LpStatus.ITERATION_LIMIT)


class WarmStart(unittest.TestCase):
    def base_problem(self, limit: float):
        return make_problem(
            [-2.0, -3.0, -1.0],
            a_ub=[[1.0, 1.0, 1.0], [2.0, 1.0, 0.0], [0.0, 1.0, 2.0]],
            b_ub=[limit, 8.0, 9.0],
            upper=[5.0, 5.0, 5.0],
        )

    def test_warm_start_matches_cold_start(self):
        first = solve(self.base_problem(6.0))
        self.assertIs(first.status, LpStatus.OPTIMAL)
        changed = self.base_problem(7.5)
        cold = solve(changed)
        warm = solve(changed, warm_basis=first.basis)
        self.assertIs(warm.status, LpStatus.OPTIMAL)
        self.assertAlmostEqual(warm.objective, cold.objective, places=9)
        self.assertLess(warm.residual, 1e-9)

    def test_warm_start_after_bound_change(self):
        first = solve(self.base_problem(6.0))
        tighter = make_problem(
            [-2.0, -3.0, -1.0],
            a_ub=[[1.0, 1.0, 1.0], [2.0, 1.0, 0.0], [0.0, 1.0, 2.0]],
            b_ub=[6.0, 8.0, 9.0],
            upper=[5.0, 2.0, 5.0],
        )
        cold = solve(tighter)
        warm = solve(tighter, warm_basis=first.basis)
        self.assertAlmostEqual(warm.objective, cold.objective, places=9)

    def test_bad_warm_basis_is_rejected(self):
        with self.assertRaises(ValueError):
            solve(self.base_problem(6.0), warm_basis=(0, 1))


class InputChecks(unittest.TestCase):
    def test_nan_is_rejected(self):
        with self.assertRaises(LpProblemError):
            make_problem([1.0, float("nan")])

    def test_size_mismatch_is_rejected(self):
        with self.assertRaises(LpProblemError):
            make_problem([1.0, 2.0], a_ub=[[1.0, 1.0]], b_ub=[1.0, 2.0])

    def test_lower_above_upper_is_rejected(self):
        with self.assertRaises(LpProblemError):
            make_problem([1.0], lower=[2.0], upper=[1.0])

    def test_empty_problem_is_rejected(self):
        with self.assertRaises(LpProblemError):
            make_problem([])


class NoThirdPartySolvers(unittest.TestCase):
    def test_sources_do_not_mention_solvers(self):
        for path in sorted(PACKAGE.rglob("*.py")):
            text = path.read_text(encoding="utf-8").lower()
            for name in FORBIDDEN_SOLVERS:
                if name == "scipy" and path.name == "__init__.py":
                    continue
                with self.subTest(module=path.name, name=name):
                    self.assertNotIn(f"import {name}", text)


if __name__ == "__main__":
    unittest.main()
