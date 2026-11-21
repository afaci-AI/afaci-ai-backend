"""Expiry of the temporary password sent to a new user.

Revision ID: 9e5a3c7b1d42
Revises: 8d4f2b6a9c31
"""

import sqlalchemy as sa

from alembic import op

revision = "9e5a3c7b1d42"
down_revision = "8d4f2b6a9c31"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "temp_password_expires_at", sa.DateTime(timezone=True), nullable=True
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "temp_password_expires_at")
