"""Add price_per_kg to saved_recipe_items

Revision ID: a3f8c1d2e5b7
Revises: e2a1b7c4d9f0
Create Date: 2026-06-25

Цена сырья (руб/кг) на ингредиент сохранённой рецептуры — опциональное поле
для режима расчёта стоимости рецептуры.
"""
from alembic import op
import sqlalchemy as sa

revision = "a3f8c1d2e5b7"
down_revision = "e2a1b7c4d9f0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "saved_recipe_items",
        sa.Column("price_per_kg", sa.Double(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("saved_recipe_items", "price_per_kg")
