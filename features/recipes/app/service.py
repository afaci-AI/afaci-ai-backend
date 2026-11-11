"""Сценарии сохранённых рецептур и групп пользователя."""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from core.errors import BadRequestError, NotFoundError

from ..domain import (
    RankingWeights,
    Recipe,
    RecipeGroup,
    RecipeItem,
    metrics_from_report,
    rank_recipes,
)
from .ports import MetricsCalculator, RecipeRepository

RECIPE_NOT_FOUND = "Рецептура не найдена."
GROUP_NOT_FOUND = "Группа не найдена."


@dataclass
class ItemData:
    product_id: UUID
    amount_g: float
    price_per_kg: float | None = None


@dataclass
class RecipeChanges:
    """Частичное изменение: применяются только поля из `provided`."""

    name: str | None = None
    group_id: UUID | None = None
    reference_protein_id: UUID | None = None
    items: list[ItemData] | None = None
    draft: bool | None = None
    provided: set[str] = field(default_factory=set)


def _compute_items(items) -> list[dict]:
    return [{"product_id": it.product_id, "amount_g": it.amount_g} for it in items]


def _recipe_items(items: list[ItemData]) -> list[RecipeItem]:
    return [
        RecipeItem(
            product_id=it.product_id,
            amount_g=it.amount_g,
            sort_order=idx,
            price_per_kg=it.price_per_kg,
        )
        for idx, it in enumerate(items)
    ]


class RecipeService:
    def __init__(self, repo: RecipeRepository, calculator: MetricsCalculator) -> None:
        self._repo = repo
        self._calculator = calculator

    # ----------------------------------------------------------- группы
    async def list_groups(self, user_id: UUID) -> list[tuple[RecipeGroup, int]]:
        return await self._repo.list_groups(user_id)

    async def create_group(self, user_id: UUID, name: str) -> RecipeGroup:
        return await self._repo.add_group(user_id, name.strip())

    async def rename_group(self, user_id: UUID, group_id: UUID, name: str):
        group = await self._repo.rename_group(user_id, group_id, name.strip())
        if group is None:
            raise NotFoundError(GROUP_NOT_FOUND)
        return group

    async def delete_group(self, user_id: UUID, group_id: UUID) -> None:
        if not await self._repo.delete_group(user_id, group_id):
            raise NotFoundError(GROUP_NOT_FOUND)

    async def _require_group(self, user_id: UUID, group_id: UUID) -> None:
        if not await self._repo.group_exists(user_id, group_id):
            raise NotFoundError(GROUP_NOT_FOUND)

    # -------------------------------------------------------- рецептуры
    async def list_recipes(self, user_id: UUID, group_id: UUID | None) -> list[Recipe]:
        return await self._repo.list_recipes(user_id, group_id)

    async def get_recipe(self, user_id: UUID, recipe_id: UUID) -> Recipe:
        recipe = await self._repo.get_recipe(user_id, recipe_id, with_items=True)
        if recipe is None:
            raise NotFoundError(RECIPE_NOT_FOUND)
        return recipe

    async def create_recipe(
        self,
        user_id: UUID,
        *,
        name: str,
        reference_protein_id: UUID,
        items: list[ItemData],
        draft: bool,
        group_id: UUID | None,
        new_group_name: str | None,
    ) -> Recipe:
        report = None
        if not draft:
            report = await self._calculator.compute(
                reference_protein_id, _compute_items(items)
            )

        group_name = new_group_name.strip() if new_group_name else ""
        if group_name:
            group_id = None
        elif group_id is not None:
            await self._require_group(user_id, group_id)

        recipe = Recipe(
            name=name.strip(),
            reference_protein_id=reference_protein_id,
            group_id=group_id,
            items=_recipe_items(items),
        )
        if report:
            recipe.apply_metrics(metrics_from_report(report))
        return await self._repo.create_recipe(user_id, recipe, group_name or None)

    async def update_recipe(
        self, user_id: UUID, recipe_id: UUID, changes: RecipeChanges
    ) -> Recipe:
        recipe = await self.get_recipe(user_id, recipe_id)
        provided = changes.provided

        if "name" in provided and changes.name is not None:
            recipe.rename(changes.name.strip())

        if "group_id" in provided:
            if changes.group_id is not None:
                await self._require_group(user_id, changes.group_id)
            recipe.group_id = changes.group_id

        make_draft = changes.draft is True
        new_ref = (
            changes.reference_protein_id
            if "reference_protein_id" in provided and changes.reference_protein_id
            else recipe.reference_protein_id
        )
        if "items" in provided and changes.items is not None:
            recipe.reference_protein_id = new_ref
            await self._recalculate(recipe, new_ref, changes.items, make_draft)
            recipe.replace_items(_recipe_items(changes.items))
        elif "reference_protein_id" in provided and changes.reference_protein_id:
            recipe.reference_protein_id = new_ref
            await self._recalculate(recipe, new_ref, recipe.sorted_items(), make_draft)

        return await self._repo.save_recipe(user_id, recipe)

    async def _recalculate(self, recipe: Recipe, reference_id, items, draft: bool):
        if draft:
            recipe.clear_metrics()
            return
        report = await self._calculator.compute(reference_id, _compute_items(items))
        recipe.apply_metrics(metrics_from_report(report))

    async def delete_recipe(self, user_id: UUID, recipe_id: UUID) -> None:
        if not await self._repo.delete_recipe(user_id, recipe_id):
            raise NotFoundError(RECIPE_NOT_FOUND)

    # ----------------------------------------------------- ранжирование
    async def rank(
        self, user_id: UUID, recipe_ids: list[UUID], weights: RankingWeights
    ) -> dict:
        if len(recipe_ids) < 1:
            raise BadRequestError("Выберите хотя бы одну рецептуру.")
        recipes = await self._repo.find_recipes(user_id, recipe_ids)
        if len(recipes) != len(set(recipe_ids)):
            raise NotFoundError("Некоторые рецептуры не найдены.")
        group_names = await self._repo.group_names(user_id)
        return rank_recipes(recipes, group_names, weights)
