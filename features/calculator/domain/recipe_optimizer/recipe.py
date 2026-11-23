"""Проверенный состав: массы, показатели, стоимость и нарушения порогов."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class EvaluatedRecipe:
    amounts: np.ndarray
    quality: dict
    cost: float
    violations: np.ndarray
