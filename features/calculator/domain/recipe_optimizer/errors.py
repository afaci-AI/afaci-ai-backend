"""Ошибки и константы поиска состава."""

COMPARISON_TOLERANCE = 1e-6
METRICS = ("bc", "U", "G")


class RecipeOptimizationError(ValueError):
    def __init__(self, detail: str, code: str = "invalid_optimization_data"):
        super().__init__(detail)
        self.code = code
