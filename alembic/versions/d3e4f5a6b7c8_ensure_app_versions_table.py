"""Ensure app_versions table exists (repair for stamped-but-missing state)

Revision ID: d3e4f5a6b7c8
Revises: d1e2f3a4b5c6
Create Date: 2026-09-01

На существующих БД alembic_version мог быть заштампован на head
(d1e2f3a4b5c6) во время выравнивания цепочки миграций, при этом сама
таблица app_versions физически не была создана — docker-entrypoint
выполнял alembic upgrade head как no-op, и эндпоинты версий падали с
UndefinedTableError.

Миграция идемпотентна: если таблицы нет — создаёт её с той же структурой,
что и d1e2f3a4b5c6; если есть — сверяет набор колонок и пишет
предупреждение при расхождении, не прерывая деплой (как f4d8a2c6b3e1).
"""

import warnings

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "d3e4f5a6b7c8"
down_revision = "d1e2f3a4b5c6"
branch_labels = None
depends_on = None


_TABLE_NAME = "app_versions"

_EXPECTED_COLUMNS = {
    "id",
    "version",
    "version_code",
    "apk_url",
    "apk_filename",
    "changelog",
    "force_update",
    "min_supported_version_code",
    "is_current",
    "published_at",
}


def upgrade() -> None:
    existing = set(sa.inspect(op.get_bind()).get_table_names())
    if _TABLE_NAME in existing:
        _verify_existing()
        return

    op.create_table(
        _TABLE_NAME,
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
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "published_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_app_versions_is_current", _TABLE_NAME, ["is_current"], unique=False
    )


def _verify_existing() -> None:
    actual = {col["name"] for col in sa.inspect(op.get_bind()).get_columns(_TABLE_NAME)}
    missing = sorted(_EXPECTED_COLUMNS - actual)
    if missing:
        warnings.warn(
            f"Таблица '{_TABLE_NAME}' уже существует, но структура отличается: "
            f"отсутствуют колонки {missing}. Совпадение не гарантировано — "
            f"проверьте таблицу вручную.",
            stacklevel=2,
        )


def downgrade() -> None:
    op.drop_index("ix_app_versions_is_current", table_name=_TABLE_NAME)
    op.drop_table(_TABLE_NAME)
