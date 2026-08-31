"""Add users, recipe_groups, saved_recipes, saved_recipe_items

Revision ID: e2a1b7c4d9f0
Revises: f4d8a2c6b3e1
Create Date: 2026-06-24

Аутентификация и сохранённые пользователем рецептуры с группами (как плейлисты).

Внимание: saved_recipes имеет FOREIGN KEY на reference_proteins, поэтому эта
миграция идёт ПОСЛЕ f4d8a2c6b3e1 (создаёт эти таблицы), чтобы upgrade head
работал на свежей БД.
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

# revision identifiers, used by Alembic.
revision = "e2a1b7c4d9f0"
down_revision = "f4d8a2c6b3e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("password_hash", sa.String(), nullable=False),
        sa.Column("role", sa.String(), nullable=False, server_default="viewer"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )

    op.create_table(
        "recipe_groups",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_recipe_groups_user_id", "recipe_groups", ["user_id"])

    op.create_table(
        "saved_recipes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "group_id",
            UUID(as_uuid=True),
            sa.ForeignKey("recipe_groups.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column(
            "reference_protein_id",
            UUID(as_uuid=True),
            sa.ForeignKey("reference_proteins.id"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("bc", sa.Double(), nullable=True),
        sa.Column("kras", sa.Double(), nullable=True),
        sa.Column("v_coef", sa.Double(), nullable=True),
        sa.Column("g_coef", sa.Double(), nullable=True),
        sa.Column("energy_kcal", sa.Double(), nullable=True),
        sa.Column("c_min_name", sa.String(), nullable=True),
        sa.Column("c_min_score", sa.Double(), nullable=True),
    )
    op.create_index("ix_saved_recipes_user_id", "saved_recipes", ["user_id"])
    op.create_index("ix_saved_recipes_group_id", "saved_recipes", ["group_id"])

    op.create_table(
        "saved_recipe_items",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "saved_recipe_id",
            UUID(as_uuid=True),
            sa.ForeignKey("saved_recipes.id", ondelete="CASCADE"),
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
    )
    op.create_index(
        "ix_saved_recipe_items_recipe_id", "saved_recipe_items", ["saved_recipe_id"]
    )


def downgrade() -> None:
    op.drop_table("saved_recipe_items")
    op.drop_table("saved_recipes")
    op.drop_table("recipe_groups")
    op.drop_table("users")
