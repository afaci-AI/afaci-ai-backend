"""Add app_versions table for mobile app update checking

Revision ID: d1e2f3a4b5c6
Revises: b7c9d2f4a1e3
Create Date: 2026-08-31

Таблица app_versions хранит информацию о версиях мобильного приложения.
Текущая версия определяется флагом is_current=True.
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "d1e2f3a4b5c6"
down_revision = "b7c9d2f4a1e3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "app_versions",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("version", sa.String(), nullable=False),
        sa.Column("version_code", sa.Integer(), nullable=False, unique=True),
        sa.Column("apk_url", sa.String(), nullable=False),
        sa.Column("apk_filename", sa.String(), nullable=False),
        sa.Column("changelog", sa.String(), nullable=True),
        sa.Column(
            "force_update", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column("min_supported_version_code", sa.Integer(), nullable=True),
        sa.Column(
            "is_current", sa.Boolean(), nullable=False, server_default=sa.true()
        ),
        sa.Column(
            "published_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_app_versions_is_current", "app_versions", ["is_current"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_app_versions_is_current", table_name="app_versions")
    op.drop_table("app_versions")
