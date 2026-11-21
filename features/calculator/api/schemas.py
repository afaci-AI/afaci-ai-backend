"""Схемы запросов и ответов калькулятора."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class ReferenceSourceOut(BaseModel):
    title: str
    authors: str | None = None
    year: int | None = None
    location: str | None = None
    url: str | None = None
    pdf_url: str | None = None


class ReferenceValueOut(BaseModel):
    amino_acid: str
    value: float


class ReferenceProteinOut(BaseModel):
    id: UUID
    name: str
    year: int | None
    is_default: bool
    description: str | None
    values: list[ReferenceValueOut]
    source: ReferenceSourceOut | None = None


class CalcItem(BaseModel):
    product_id: UUID
    amount_g: float


class CalcRequest(BaseModel):
    reference_protein_id: UUID
    items: list[CalcItem]


class CandidateIn(BaseModel):
    product_id: UUID
    price_per_kg: float
    min_amount_g: float = 0.0
    max_amount_g: float = 100.0


class OptConstraints(BaseModel):
    bc_min: float | None = None
    kras_max: float | None = None


class OptimizeCostRequest(BaseModel):
    reference_protein_id: UUID
    candidates: list[CandidateIn]
    constraints: OptConstraints = OptConstraints()


class OptimizationItemIn(BaseModel):
    product_id: UUID
    amount_g: float = Field(ge=0, le=100, allow_inf_nan=False)
    price_per_kg: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    min_amount_g: float = Field(default=0.0, ge=0, le=100, allow_inf_nan=False)
    max_amount_g: float = Field(default=100.0, ge=0, le=100, allow_inf_nan=False)

    @model_validator(mode="after")
    def validate_range(self):
        if self.min_amount_g > self.max_amount_g:
            raise ValueError("Минимальная доля ингредиента превышает максимальную.")
        return self


class OptimizeRecipeRequest(BaseModel):
    mode: Literal["basic", "cost"]
    reference_protein_id: UUID
    items: list[OptimizationItemIn] = Field(min_length=1, max_length=50)

    @model_validator(mode="after")
    def validate_recipe(self):
        if len({item.product_id for item in self.items}) != len(self.items):
            raise ValueError("Ингредиенты рецептуры не должны повторяться.")
        if abs(sum(item.amount_g for item in self.items) - 100.0) > 0.01:
            raise ValueError("Сумма исходной рецептуры должна быть 100 г (±0.01 г).")
        if sum(item.min_amount_g for item in self.items) > 100.0 + 1e-6:
            raise ValueError("Сумма минимальных долей превышает 100 г.")
        if sum(item.max_amount_g for item in self.items) < 100.0 - 1e-6:
            raise ValueError("Сумма максимальных долей меньше 100 г.")
        if self.mode == "cost" and any(
            item.price_per_kg is None for item in self.items
        ):
            raise ValueError(
                "Для оптимизации по цене укажите цену каждого ингредиента."
            )
        return self
