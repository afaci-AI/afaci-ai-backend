"""Add fixed unit to nutrient names (nutrients_names.unit_id).

Единица измерения принадлежит названию нутриента. Значения единиц у уже
сохранённых нутриентов не меняются и не пересчитываются.

Заполнение существующих названий:
  * у названия есть значения и все они в одной единице — берётся она;
  * значений нет — единица по типу состава («Химический состав» — %/100г,
    «Аминокислотный состав» и «Минеральный состав» — мг/100г);
  * значения в разных единицах — остаётся NULL: единицу нужно выбрать вручную,
    миграция её не угадывает.

Revision ID: b8c9d0e1f2a3
Revises: f6a7b8c9d0e1
"""

import sqlalchemy as sa

from alembic import op

revision = "b8c9d0e1f2a3"
down_revision = "f6a7b8c9d0e1"
branch_labels = None
depends_on = None

CHEMICAL = "Химический состав"
AMINO = "Аминокислотный состав"
MINERAL = "Минеральный состав"
PERCENT = "%/100г"
MILLIGRAMS = "мг/100г"


def upgrade() -> None:
    op.add_column("nutrients_names", sa.Column("unit_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "fk_nutrients_names_unit_id", "nutrients_names", "units", ["unit_id"], ["id"]
    )
    bind = op.get_bind()
    bind.execute(
        sa.text(
            """
            UPDATE nutrients_names nn
            SET unit_id = used.unit_id
            FROM (
                SELECT id_name_component AS name_id,
                       (array_agg(DISTINCT unit_id))[1] AS unit_id
                FROM nutrients
                GROUP BY id_name_component
                HAVING count(DISTINCT unit_id) = 1
            ) used
            WHERE nn.id = used.name_id
            """
        )
    )
    bind.execute(
        sa.text(
            """
            UPDATE nutrients_names nn
            SET unit_id = u.id
            FROM nutrients_types t, units u
            WHERE nn.unit_id IS NULL
              AND t.id = nn.nutrient_type_id
              AND NOT EXISTS (
                  SELECT 1 FROM nutrients n WHERE n.id_name_component = nn.id
              )
              AND (
                  (t.name = :chemical AND u.name = :percent)
                  OR (t.name IN (:amino, :mineral) AND u.name = :milligrams)
              )
            """
        ),
        {
            "chemical": CHEMICAL,
            "amino": AMINO,
            "mineral": MINERAL,
            "percent": PERCENT,
            "milligrams": MILLIGRAMS,
        },
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_nutrients_names_unit_id", "nutrients_names", type_="foreignkey"
    )
    op.drop_column("nutrients_names", "unit_id")
