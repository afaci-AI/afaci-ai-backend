"""Работа с базисной матрицей: решение систем и повторное разложение.

Хранится обратная матрица базиса. Шаг симплекс-метода обновляет её в
произведённой форме (исключение Гаусса по ведущему элементу), а каждые
`refactor_every` шагов и при росте невязки она пересчитывается заново из
столбцов базиса — это удерживает накопленную ошибку.

NumPy используется только как линейная алгебра (`numpy.linalg.solve`):
симплекс-метода в нём нет.
"""

import numpy as np

from .problem import Matrix, Vector

DEFAULT_REFACTOR_EVERY = 50


class SingularBasisError(RuntimeError):
    """Базисная матрица вырождена: решение продолжить нельзя."""


class Basis:
    """Базис рабочей формы: индексы столбцов и обратная матрица."""

    def __init__(
        self,
        matrix: Matrix,
        indices: list[int],
        *,
        refactor_every: int = DEFAULT_REFACTOR_EVERY,
    ) -> None:
        self._matrix = matrix
        self.indices = list(indices)
        self._refactor_every = max(1, refactor_every)
        self._updates = 0
        self.refactor()

    @property
    def size(self) -> int:
        return len(self.indices)

    def refactor(self) -> None:
        """Пересчитать обратную матрицу из текущих столбцов базиса."""
        if not self.indices:
            self._inverse = np.zeros((0, 0))
            self._updates = 0
            return
        columns = self._matrix[:, self.indices]
        try:
            self._inverse = np.linalg.solve(columns, np.eye(self.size))
        except np.linalg.LinAlgError as error:
            raise SingularBasisError(str(error)) from error
        self._updates = 0

    def ftran(self, column: Vector) -> Vector:
        """B⁻¹·a — представление столбца в базисе."""
        return self._inverse @ column

    def btran(self, costs: Vector) -> Vector:
        """B⁻ᵀ·c_B — двойственные оценки строк."""
        return self._inverse.T @ costs

    def tableau_row(self, position: int) -> Vector:
        """Строка симплекс-таблицы: eᵢᵀ·B⁻¹·A."""
        return self._inverse[position] @ self._matrix

    def replace(self, position: int, entering: int, direction: Vector) -> None:
        """Заменить переменную в базисе; `direction` — B⁻¹ столбца `entering`."""
        pivot = direction[position]
        if abs(pivot) < 1e-12:
            raise SingularBasisError("ведущий элемент близок к нулю")
        self.indices[position] = entering
        self._inverse[position] /= pivot
        factors = direction.copy()
        factors[position] = 0.0
        self._inverse -= np.outer(factors, self._inverse[position])
        self._updates += 1
        if self._updates >= self._refactor_every:
            self.refactor()

    def inverse_error(self) -> float:
        """Невязка ‖B·B⁻¹ − I‖∞ — признак, что пора пересчитать разложение."""
        if not self.indices:
            return 0.0
        product = self._matrix[:, self.indices] @ self._inverse
        return float(np.abs(product - np.eye(self.size)).max())
