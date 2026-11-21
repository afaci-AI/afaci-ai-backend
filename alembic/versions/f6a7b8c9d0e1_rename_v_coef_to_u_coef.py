"""Rename saved_recipes.v_coef to u_coef (utility coefficient is denoted U).

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
"""

from alembic import op

revision = "f6a7b8c9d0e1"
down_revision = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("saved_recipes", "v_coef", new_column_name="u_coef")


def downgrade() -> None:
    op.alter_column("saved_recipes", "u_coef", new_column_name="v_coef")
