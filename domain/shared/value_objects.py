from dataclasses import dataclass


@dataclass(frozen=True)
class Weight:
    grams: float

    def __post_init__(self) -> None:
        if self.grams < 0:
            raise ValueError(f"Масса не может быть отрицательной: {self.grams}")


@dataclass(frozen=True)
class Percentage:
    value: float

    def __post_init__(self) -> None:
        if not 0 <= self.value <= 100:
            raise ValueError(f"Процент должен быть от 0 до 100: {self.value}")
