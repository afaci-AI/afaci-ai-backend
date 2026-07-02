class DomainError(Exception):
    pass


class InvalidRecipeSumError(DomainError):
    def __init__(self, actual: float, expected: float = 100.0) -> None:
        self.actual = actual
        self.expected = expected
        super().__init__(
            f"Сумма Xᵢ должна быть {expected:.0f} г, получено {actual:.2f} г"
        )


class EmptyRecipeError(DomainError):
    pass


class ReferenceProteinNotFoundError(DomainError):
    pass


class OptimizationInfeasibleError(DomainError):
    def __init__(self, detail: str = "") -> None:
        msg = "Задача оптимизации не имеет допустимого решения."
        if detail:
            msg += f" {detail}"
        super().__init__(msg)
        self.detail = msg
