"""Add reference_proteins, reference_protein_values, recipes, recipe_items

Revision ID: f4d8a2c6b3e1
Revises: d1e2f3a4b5c6
Create Date: 2026-07-02

Эти таблицы использует калькулятор (domain/calculator), но раньше их
создавали вручную через seed_calculator.sql в обход alembic — на свежей
БД (например, в docker) upgrade head падал, т.к. saved_recipes (миграция
e2a1b7c4d9f0) ссылается на reference_proteins, которой ещё не существует.

Внимание: эта миграция идёт ПЕРЕД e2a1b7c4d9f0 (users/saved_recipes),
т.к. последняя создаёт FOREIGN KEY на reference_proteins. Раньше эта
миграция была вторым head'ом и ломала upgrade head на свежей БД; теперь
цепочка строго линейна.

Миграция идемпотентна: на существующих БД (где таблицы уже созданы
вручную через seed_calculator.sql) она не выполняет CREATE TABLE, а лишь
сверяет фактическую структуру с ожидаемой и пишет предупреждение при
расхождении (не прерывая деплой). На свежих БД таблицы создаются штатно.
"""

import warnings

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

# revision identifiers, used by Alembic.
revision = "f4d8a2c6b3e1"
down_revision = "c6ef9e3d7f1a"
branch_labels = None
depends_on = None

_UUID = UUID(as_uuid=True)


def _build_reference_proteins():
    return (
        sa.Column("id", _UUID, primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column(
            "is_default", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column("description", sa.Text(), nullable=True),
        sa.UniqueConstraint("name"),
    )


def _build_reference_protein_values():
    return (
        sa.Column("id", _UUID, primary_key=True),
        sa.Column(
            "reference_protein_id",
            _UUID,
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


def _build_recipes():
    return (
        sa.Column("id", _UUID, primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "sample_type", sa.String(), nullable=False, server_default="контроль"
        ),
        sa.UniqueConstraint("name"),
    )


def _build_recipe_items():
    return (
        sa.Column("id", _UUID, primary_key=True),
        sa.Column(
            "recipe_id",
            _UUID,
            sa.ForeignKey("recipes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "product_id",
            _UUID,
            sa.ForeignKey("products.id"),
            nullable=False,
        ),
        sa.Column("amount_g", sa.Double(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("recipe_id", "product_id", name="uq_recipe_product"),
    )


_TABLE_BUILDERS = {
    "reference_proteins": _build_reference_proteins,
    "reference_protein_values": _build_reference_protein_values,
    "recipes": _build_recipes,
    "recipe_items": _build_recipe_items,
}

# Ожидаемый набор колонок для каждой существующей таблицы (для сверки структуры).
_EXPECTED_COLUMNS = {
    "reference_proteins": {"id", "name", "year", "is_default", "description"},
    "reference_protein_values": {
        "id",
        "reference_protein_id",
        "amino_acid",
        "value",
        "sort_order",
    },
    "recipes": {"id", "name", "description", "sample_type"},
    "recipe_items": {"id", "recipe_id", "product_id", "amount_g", "sort_order"},
}


def upgrade() -> None:
    bind = op.get_bind()
    existing = set(sa.inspect(bind).get_table_names())

    for table_name, builder in _TABLE_BUILDERS.items():
        if table_name in existing:
            _verify_existing(table_name)
            continue
        op.create_table(table_name, *builder())


def _verify_existing(table_name: str) -> None:
    """Сверяет структуру уже существующей таблицы с ожидаемой.

    Идемпотентное поведение: если таблица создана из seed_calculator.sql,
    структура совпадает и миграция молча пропускает CREATE TABLE. Если
    выявлено расхождение (ручные правки схемы), пишем предупреждение в лог,
    но НЕ прерываем деплой — подразумеваем, что расхождение осознанное.
    """
    actual = {col["name"] for col in sa.inspect(op.get_bind()).get_columns(table_name)}
    expected = _EXPECTED_COLUMNS[table_name]
    missing = sorted(expected - actual)
    if missing:
        warnings.warn(
            f"Таблица '{table_name}' уже существует, но структура отличается: "
            f"отсутствуют колонки {missing}. Совпадение не гарантировано — "
            f"проверьте таблицу вручную.",
            stacklevel=2,
        )


def downgrade() -> None:
    op.drop_table("recipe_items")
    op.drop_table("recipes")
    op.drop_table("reference_protein_values")
    op.drop_table("reference_proteins")
