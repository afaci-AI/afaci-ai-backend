"""Порты рецептур: хранилище и расчёт метрик."""

from typing import Protocol
from uuid import UUID

from ..domain import Recipe, RecipeGroup


class RecipeRepository(Protocol):
    # ----------------------------------------------------------- группы
    async def list_groups(self, user_id: UUID) -> list[tuple[RecipeGroup, int]]:
        """Группы пользователя по дате создания с числом рецептур."""

    async def group_exists(self, user_id: UUID, group_id: UUID) -> bool: ...

    async def add_group(self, user_id: UUID, name: str) -> RecipeGroup: ...

    async def rename_group(
        self, user_id: UUID, group_id: UUID, name: str
    ) -> RecipeGroup | None: ...

    async def delete_group(self, user_id: UUID, group_id: UUID) -> bool:
        """Удаляет группу; её рецептуры остаются без группы. False, если группы нет."""

    async def group_names(self, user_id: UUID) -> dict[UUID, str]: ...

    # -------------------------------------------------------- рецептуры
    async def list_recipes(self, user_id: UUID, group_id: UUID | None) -> list[Recipe]:
        """Без состава, по убыванию даты изменения."""

    async def get_recipe(
        self, user_id: UUID, recipe_id: UUID, *, with_items: bool
    ) -> Recipe | None: ...

    async def find_recipes(self, user_id: UUID, ids: list[UUID]) -> list[Recipe]: ...

    async def create_recipe(
        self, user_id: UUID, recipe: Recipe, new_group_name: str | None
    ) -> Recipe:
        """Сохраняет рецептуру (и новую группу в той же транзакции)."""

    async def save_recipe(self, user_id: UUID, recipe: Recipe) -> Recipe:
        """Записывает изменения; состав заменяется, если `recipe.items_changed`."""

    async def delete_recipe(self, user_id: UUID, recipe_id: UUID) -> bool: ...


class MetricsCalculator(Protocol):
    async def compute(self, reference_protein_id: UUID, items: list[dict]) -> dict:
        """Отчёт калькулятора для состава [{product_id, amount_g}]."""
