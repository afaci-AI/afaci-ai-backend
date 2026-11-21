"""Add nutrients_names.nutrient_class (macro | micro | amino | other).

Revision ID: a1b2c3d4e5f7
Revises: c9d0e1f2a3b4
"""

import sqlalchemy as sa

from alembic import op

revision = "a1b2c3d4e5f7"
down_revision = "c9d0e1f2a3b4"
branch_labels = None
depends_on = None

CHECK = "ck_nutrient_name_class"


def upgrade() -> None:
    op.add_column(
        "nutrients_names",
        sa.Column(
            "nutrient_class", sa.String(), nullable=False, server_default="other"
        ),
    )
    op.execute(
        """
        UPDATE nutrients_names n SET nutrient_class = CASE t.name
            WHEN 'Аминокислотный состав' THEN 'amino'
            WHEN 'Минеральный состав' THEN 'micro'
            ELSE 'other' END
        FROM nutrients_types t WHERE t.id = n.nutrient_type_id
        """
    )
    op.execute(
        """
        UPDATE nutrients_names n SET nutrient_class = 'macro'
        FROM nutrients_types t
        WHERE t.id = n.nutrient_type_id AND t.name = 'Химический состав'
          AND n.name IN ('Массовая доля белка', 'Массовая доля жира',
                         'Углеводы', 'Пищевые волокна')
        """
    )
    op.create_check_constraint(
        CHECK,
        "nutrients_names",
        "nutrient_class IN ('macro', 'micro', 'amino', 'other')",
    )


def downgrade() -> None:
    op.drop_constraint(CHECK, "nutrients_names", type_="check")
    op.drop_column("nutrients_names", "nutrient_class")
