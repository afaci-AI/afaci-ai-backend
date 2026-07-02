"""Add access_expires_at and must_change_password to users

Revision ID: b7c9d2f4a1e3
Revises: a3f8c1d2e5b7
Create Date: 2026-07-02

Срок действия учётной записи (nullable — пусто значит безлимитный доступ)
и флаг принудительной смены пароля при первом входе.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "b7c9d2f4a1e3"
down_revision = "a3f8c1d2e5b7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("access_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "users",
        sa.Column("must_change_password", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("users", "must_change_password")
    op.drop_column("users", "access_expires_at")
