"""SQL-реализация хранилища сохранённых рецептур."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.db.models import RecipeGroup as GroupRow
from core.db.models import SavedRecipe as RecipeRow

from ..domain import Recipe, RecipeGroup
from .mapper import apply_metrics, to_group, to_item_row, to_recipe


class SqlRecipeRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ----------------------------------------------------------- группы
    async def _group_row(self, user_id: UUID, group_id: UUID) -> GroupRow | None:
        return (
            await self._db.execute(
                select(GroupRow).where(
                    GroupRow.id == group_id, GroupRow.user_id == user_id
                )
            )
        ).scalar_one_or_none()

    async def list_groups(self, user_id: UUID) -> list[tuple[RecipeGroup, int]]:
        groups = (
            (
                await self._db.execute(
                    select(GroupRow)
                    .where(GroupRow.user_id == user_id)
                    .order_by(GroupRow.created_at)
                )
            )
            .scalars()
            .all()
        )
        counts = dict(
            (
                await self._db.execute(
                    select(RecipeRow.group_id, func.count())
                    .where(RecipeRow.user_id == user_id, RecipeRow.group_id.isnot(None))
                    .group_by(RecipeRow.group_id)
                )
            ).all()
        )
        return [(to_group(g), counts.get(g.id, 0)) for g in groups]

    async def group_exists(self, user_id: UUID, group_id: UUID) -> bool:
        return await self._group_row(user_id, group_id) is not None

    async def add_group(self, user_id: UUID, name: str) -> RecipeGroup:
        row = GroupRow(user_id=user_id, name=name)
        self._db.add(row)
        await self._db.commit()
        await self._db.refresh(row)
        return to_group(row)

    async def rename_group(
        self, user_id: UUID, group_id: UUID, name: str
    ) -> RecipeGroup | None:
        row = await self._group_row(user_id, group_id)
        if row is None:
            return None
        row.name = name
        await self._db.commit()
        await self._db.refresh(row)
        return to_group(row)

    async def delete_group(self, user_id: UUID, group_id: UUID) -> bool:
        row = await self._group_row(user_id, group_id)
        if row is None:
            return False
        await self._db.execute(
            RecipeRow.__table__.update()
            .where(RecipeRow.group_id == group_id)
            .values(group_id=None)
        )
        await self._db.delete(row)
        await self._db.commit()
        return True

    async def group_names(self, user_id: UUID) -> dict[UUID, str]:
        rows = (
            (
                await self._db.execute(
                    select(GroupRow).where(GroupRow.user_id == user_id)
                )
            )
            .scalars()
            .all()
        )
        return {g.id: g.name for g in rows}

    # -------------------------------------------------------- рецептуры
    async def _recipe_row(
        self, user_id: UUID, recipe_id: UUID, *, with_items: bool
    ) -> RecipeRow | None:
        stmt = select(RecipeRow).where(
            RecipeRow.id == recipe_id, RecipeRow.user_id == user_id
        )
        if with_items:
            stmt = stmt.options(selectinload(RecipeRow.items))
        return (await self._db.execute(stmt)).scalar_one_or_none()

    async def list_recipes(self, user_id: UUID, group_id: UUID | None) -> list[Recipe]:
        stmt = select(RecipeRow).where(RecipeRow.user_id == user_id)
        if group_id is not None:
            stmt = stmt.where(RecipeRow.group_id == group_id)
        stmt = stmt.order_by(RecipeRow.updated_at.desc())
        rows = (await self._db.execute(stmt)).scalars().all()
        return [to_recipe(r, with_items=False) for r in rows]

    async def get_recipe(
        self, user_id: UUID, recipe_id: UUID, *, with_items: bool
    ) -> Recipe | None:
        row = await self._recipe_row(user_id, recipe_id, with_items=with_items)
        return None if row is None else to_recipe(row, with_items=with_items)

    async def find_recipes(self, user_id: UUID, ids: list[UUID]) -> list[Recipe]:
        rows = (
            (
                await self._db.execute(
                    select(RecipeRow).where(
                        RecipeRow.user_id == user_id, RecipeRow.id.in_(ids)
                    )
                )
            )
            .scalars()
            .all()
        )
        return [to_recipe(r, with_items=False) for r in rows]

    async def create_recipe(
        self, user_id: UUID, recipe: Recipe, new_group_name: str | None
    ) -> Recipe:
        group_id = recipe.group_id
        if new_group_name:
            group = GroupRow(user_id=user_id, name=new_group_name)
            self._db.add(group)
            await self._db.flush()
            group_id = group.id
        row = RecipeRow(
            user_id=user_id,
            group_id=group_id,
            name=recipe.name,
            reference_protein_id=recipe.reference_protein_id,
        )
        apply_metrics(row, recipe.metrics)
        for item in recipe.items:
            row.items.append(to_item_row(item))
        self._db.add(row)
        await self._db.commit()
        await self._db.refresh(row)
        return to_recipe(row, with_items=False)

    async def save_recipe(self, user_id: UUID, recipe: Recipe) -> Recipe:
        row = await self._recipe_row(user_id, recipe.id, with_items=True)
        row.name = recipe.name
        row.group_id = recipe.group_id
        row.reference_protein_id = recipe.reference_protein_id
        apply_metrics(row, recipe.metrics)
        if recipe.items_changed:
            row.items.clear()
            for item in recipe.items:
                row.items.append(to_item_row(item))
        await self._db.commit()
        await self._db.refresh(row)
        return to_recipe(row, with_items=False)

    async def delete_recipe(self, user_id: UUID, recipe_id: UUID) -> bool:
        row = await self._recipe_row(user_id, recipe_id, with_items=False)
        if row is None:
            return False
        await self._db.delete(row)
        await self._db.commit()
        return True
