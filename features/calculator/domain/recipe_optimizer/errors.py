"""Ошибки и константы поиска состава."""

COMPARISON_TOLERANCE = 1e-6
METRICS = ("bc", "U", "G")

# Стоимость считается на 100 г; интерфейсу нужна цена за килограмм.
PER_KILOGRAM = 10.0


class RecipeOptimizationError(ValueError):
    def __init__(self, detail: str, code: str = "invalid_optimization_data"):
        super().__init__(detail)
        self.code = code
