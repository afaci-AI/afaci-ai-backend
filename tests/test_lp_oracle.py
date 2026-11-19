"""Эталон для модуля ЛП: перебор вершин на точных дробях.

Сторонние решатели не используются даже в тестах — их тоже пришлось бы
проверять. Эталон считает все вершины допустимой области в арифметике
`fractions.Fraction` и выбирает лучшую: для малых задач это точный ответ,
с которым сравнивается двойственный симплекс-метод.
"""

import random
import unittest
from fractions import Fraction
from itertools import combinations

from libs.lp import LpStatus, make_problem, solve

PROBLEMS = 200
SEED = 20261119
TOLERANCE = Fraction(1, 10**9)


def _gauss(rows: list[list[Fraction]], rhs: list[Fraction]):
    """Решить систему точно; None, если матрица вырождена."""
    size = len(rhs)
    table = [list(row) + [value] for row, value in zip(rows, rhs)]
    for column in range(size):
        pivot = next(
            (index for index in range(column, size) if table[index][column]), None
        )
        if pivot is None:
            return None
        table[column], table[pivot] = table[pivot], table[column]
        divisor = table[column][column]
        table[column] = [item / divisor for item in table[column]]
        for index in range(size):
            if index != column and table[index][column]:
                factor = table[index][column]
                table[index] = [
                    item - factor * base
                    for item, base in zip(table[index], table[column])
                ]
    return [row[size] for row in table]


def _planes(problem) -> list[tuple[list[Fraction], Fraction]]:
    """Гиперплоскости-кандидаты: строки «≤» и границы переменных."""
    planes = []
    for row, value in zip(problem["a_ub"], problem["b_ub"]):
        planes.append(([Fraction(item) for item in row], Fraction(value)))
    size = len(problem["cost"])
    for index in range(size):
        axis = [Fraction(0)] * size
        axis[index] = Fraction(1)
        planes.append((list(axis), Fraction(problem["lower"][index])))
        planes.append((list(axis), Fraction(problem["upper"][index])))
    return planes


def _feasible(problem, point: list[Fraction]) -> bool:
    for row, value in zip(problem["a_ub"], problem["b_ub"]):
        total = sum(Fraction(item) * value_x for item, value_x in zip(row, point))
        if total > Fraction(value) + TOLERANCE:
            return False
    for row, value in zip(problem["a_eq"], problem["b_eq"]):
        total = sum(Fraction(item) * value_x for item, value_x in zip(row, point))
        if abs(total - Fraction(value)) > TOLERANCE:
            return False
    for index, value_x in enumerate(point):
        if value_x < Fraction(problem["lower"][index]) - TOLERANCE:
            return False
        if value_x > Fraction(problem["upper"][index]) + TOLERANCE:
            return False
    return True


def best_vertex(problem) -> Fraction | None:
    """Минимум цели по всем вершинам; None, если допустимых вершин нет."""
    size = len(problem["cost"])
    fixed = [
        ([Fraction(item) for item in row], Fraction(value))
        for row, value in zip(problem["a_eq"], problem["b_eq"])
    ]
    free = size - len(fixed)
    if free < 0:
        return None
    best = None
    for choice in combinations(_planes(problem), free):
        rows = [row for row, _ in fixed] + [row for row, _ in choice]
        rhs = [value for _, value in fixed] + [value for _, value in choice]
        point = _gauss(rows, rhs)
        if point is None or not _feasible(problem, point):
            continue
        total = sum(
            Fraction(item) * value for item, value in zip(problem["cost"], point)
        )
        best = total if best is None else min(best, total)
    return best


def random_problem(rng: random.Random) -> dict:
    size = rng.choice([2, 2, 3, 3, 4])
    rows = rng.randint(1, 3)
    equalities = 1 if rng.random() < 0.25 else 0
    upper = [rng.randint(1, 10) for _ in range(size)]
    return {
        "cost": [rng.randint(-5, 5) for _ in range(size)],
        "a_ub": [[rng.randint(-3, 3) for _ in range(size)] for _ in range(rows)],
        "b_ub": [rng.randint(-2, 15) for _ in range(rows)],
        "a_eq": [[rng.randint(0, 2) for _ in range(size)] for _ in range(equalities)],
        "b_eq": [rng.randint(0, 8) for _ in range(equalities)],
        "lower": [0] * size,
        "upper": upper,
    }


class VertexOracle(unittest.TestCase):
    def test_matches_vertex_enumeration(self):
        rng = random.Random(SEED)
        optimal = 0
        infeasible = 0
        for number in range(PROBLEMS):
            data = random_problem(rng)
            expected = best_vertex(data)
            result = solve(
                make_problem(
                    data["cost"],
                    a_ub=data["a_ub"],
                    b_ub=data["b_ub"],
                    a_eq=data["a_eq"],
                    b_eq=data["b_eq"],
                    lower=data["lower"],
                    upper=data["upper"],
                )
            )
            with self.subTest(problem=number):
                if expected is None:
                    self.assertIs(result.status, LpStatus.INFEASIBLE)
                    infeasible += 1
                    continue
                self.assertIs(result.status, LpStatus.OPTIMAL)
                self.assertAlmostEqual(result.objective, float(expected), delta=1e-9)
                self.assertLess(result.residual, 1e-9)
                optimal += 1
        self.assertEqual(PROBLEMS, optimal + infeasible)
        self.assertGreater(optimal, 0)
        self.assertGreater(infeasible, 0)


if __name__ == "__main__":
    unittest.main()
