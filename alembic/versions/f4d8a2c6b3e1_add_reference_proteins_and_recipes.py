"""Add reference_proteins, reference_protein_values, recipes, recipe_items

Revision ID: f4d8a2c6b3e1
Revises: d1e2f3a4b5c6
Create Date: 2026-07-02

Эти таблицы использует калькулятор (domain/calculator), но раньше их
создавали вручную через seed_calculator.sql в обход alembic — на свежей
БД (например, в docker) upgrade head падал, т.к. saved_recipes (миграция
e2a1b7c4d9f0) ссылается на reference_proteins, которой ещё не существует.

Внимание: down_revision указывает на d1e2f3a4b5c6 (app_versions), чтобы
держать цепочку миграций строго линейной (без второго head). На БД, где
эти таблицы уже созданы вручную через seed_calculator.sql, миграцию
необходимо застэмпить (alembic stamp f4d8a2c6b3e1), а не применять.
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

# revision identifiers, used by Alembic.
revision = "f4d8a2c6b3e1"
down_revision = "d1e2f3a4b5c6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "reference_proteins",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column(
            "is_default", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column("description", sa.Text(), nullable=True),
        sa.UniqueConstraint("name"),
    )

    op.create_table(
        "reference_protein_values",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "reference_protein_id",
            UUID(as_uuid=True),
            sa.ForeignKey("reference_proteins.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("amino_acid", sa.String(), nullable=False),
        sa.Column("value", sa.Double(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint(
            "reference_protein_id", "amino_acid", name="uq_refprotein_amino"
        ),
    )

    op.create_table(
        "recipes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "sample_type", sa.String(), nullable=False, server_default="контроль"
        ),
        sa.UniqueConstraint("name"),
    )

    op.create_table(
        "recipe_items",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "recipe_id",
            UUID(as_uuid=True),
            sa.ForeignKey("recipes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "product_id",
            UUID(as_uuid=True),
            sa.ForeignKey("products.id"),
            nullable=False,
        ),
        sa.Column("amount_g", sa.Double(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("recipe_id", "product_id", name="uq_recipe_product"),
    )


def downgrade() -> None:
    op.drop_table("recipe_items")
    op.drop_table("recipes")
    op.drop_table("reference_protein_values")
    op.drop_table("reference_proteins")
