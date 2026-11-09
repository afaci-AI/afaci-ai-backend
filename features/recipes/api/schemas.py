"""Схемы запросов сохранённых рецептур."""

from uuid import UUID

from pydantic import BaseModel, Field


class GroupIn(BaseModel):
    name: str = Field(min_length=1)


class SavedItemIn(BaseModel):
    product_id: UUID
    amount_g: float
    price_per_kg: float | None = None


class SavedRecipeCreate(BaseModel):
    name: str = Field(min_length=1)
    group_id: UUID | None = None
    new_group_name: str | None = None
    reference_protein_id: UUID
    items: list[SavedItemIn]
    draft: bool = False


class SavedRecipeUpdate(BaseModel):
    name: str | None = None
    group_id: UUID | None = None
    reference_protein_id: UUID | None = None
    items: list[SavedItemIn] | None = None
    draft: bool | None = None


class Weights(BaseModel):
    bc: float = 0.25
    kras: float = 0.25
    u: float | None = None
    v: float | None = None  # устаревшее имя u; используется, если u не задан
    g: float = 0.25

    @property
    def utility(self) -> float:
        if self.u is not None:
            return self.u
        return self.v if self.v is not None else 0.25


class RankingRequest(BaseModel):
    recipe_ids: list[UUID]
    weights: Weights | None = None
