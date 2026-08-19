"""Align dictionary and nutrient relations for React UI

Revision ID: c6ef9e3d7f1a
Revises: 44bda881d613
Create Date: 2026-04-26 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c6ef9e3d7f1a"
down_revision: str | Sequence[str] | None = "44bda881d613"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_table("nutrients")
    op.drop_table("products")
    op.drop_table("subcategories")
    op.drop_table("nutrients_names")

    op.create_table(
        "subcategories",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("category_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("category_id", "name", name="uq_subcategory_category_name"),
    )

    op.create_table(
        "nutrients_names",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("nutrient_type_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["nutrient_type_id"], ["nutrients_types.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "nutrient_type_id", "name", name="uq_nutrient_name_type_name"
        ),
    )

    op.create_table(
        "products",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("category_id", sa.UUID(), nullable=False),
        sa.Column("subcategory_id", sa.UUID(), nullable=True),
        sa.Column("region_id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"]),
        sa.ForeignKeyConstraint(["region_id"], ["regions.id"]),
        sa.ForeignKeyConstraint(["subcategory_id"], ["subcategories.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", "region_id", name="uq_product_name_region"),
    )

    op.create_table(
        "nutrients",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("quantity", sa.Double(), nullable=False),
        sa.Column("product_id", sa.UUID(), nullable=False),
        sa.Column("nutrient_name_id", sa.UUID(), nullable=False),
        sa.Column("unit_id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(["nutrient_name_id"], ["nutrients_names.id"]),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.ForeignKeyConstraint(["unit_id"], ["units.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "product_id", "nutrient_name_id", name="uq_product_nutrient"
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("nutrients")
    op.drop_table("products")
    op.drop_table("nutrients_names")
    op.drop_table("subcategories")

    op.create_table(
        "subcategories",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    op.create_table(
        "nutrients_names",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    op.create_table(
        "products",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("category_id", sa.UUID(), nullable=False),
        sa.Column("subcategory_id", sa.UUID(), nullable=True),
        sa.Column("region_id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"]),
        sa.ForeignKeyConstraint(["region_id"], ["regions.id"]),
        sa.ForeignKeyConstraint(["subcategory_id"], ["subcategories.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", "region_id", name="uq_product_name_region"),
    )

    op.create_table(
        "nutrients",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("quantity", sa.Double(), nullable=True),
        sa.Column("id_product", sa.UUID(), nullable=False),
        sa.Column("id_name_component", sa.UUID(), nullable=False),
        sa.Column("id_type_component", sa.UUID(), nullable=False),
        sa.Column("unit_id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(["id_name_component"], ["nutrients_names.id"]),
        sa.ForeignKeyConstraint(["id_product"], ["products.id"]),
        sa.ForeignKeyConstraint(["id_type_component"], ["nutrients_types.id"]),
        sa.ForeignKeyConstraint(["unit_id"], ["units.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "id_product", "id_name_component", name="uq_product_nutrient"
        ),
    )
