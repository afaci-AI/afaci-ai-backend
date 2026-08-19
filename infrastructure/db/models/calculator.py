import uuid

from sqlalchemy import (
    Boolean,
    Column,
    Double,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from .base import Base


class ReferenceProtein(Base):
    """Эталонный (идеальный) белок ФАО/ВОЗ — шкала для аминокислотного скора."""

    __tablename__ = "reference_proteins"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False, unique=True)
    year = Column(Integer, nullable=True)
    is_default = Column(Boolean, nullable=False, default=False)
    description = Column(Text, nullable=True)

    values = relationship(
        "ReferenceProteinValue",
        back_populates="reference_protein",
        cascade="all, delete-orphan",
    )


class ReferenceProteinValue(Base):
    """Значение НАК эталона, г/100 г белка."""

    __tablename__ = "reference_protein_values"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    reference_protein_id = Column(
        UUID(as_uuid=True), ForeignKey("reference_proteins.id"), nullable=False
    )
    amino_acid = Column(String, nullable=False)
    value = Column(Double, nullable=False)
    sort_order = Column(Integer, nullable=False, default=0)

    reference_protein = relationship("ReferenceProtein", back_populates="values")
    __table_args__ = (
        UniqueConstraint(
            "reference_protein_id", "amino_acid", name="uq_refprotein_amino"
        ),
    )


class Recipe(Base):
    """Рецептура (контроль/опытный). База — 100 г: масса в граммах = доле Xᵢ, %."""

    __tablename__ = "recipes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False, unique=True)
    description = Column(Text, nullable=True)
    sample_type = Column(String, nullable=False, default="контроль")

    items = relationship(
        "RecipeItem", back_populates="recipe", cascade="all, delete-orphan"
    )


class RecipeItem(Base):
    """Ингредиент рецептуры: продукт + Xᵢ (граммы на 100 г)."""

    __tablename__ = "recipe_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    recipe_id = Column(UUID(as_uuid=True), ForeignKey("recipes.id"), nullable=False)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    amount_g = Column(Double, nullable=False)
    sort_order = Column(Integer, nullable=False, default=0)

    recipe = relationship("Recipe", back_populates="items")
    product = relationship("Product")
    __table_args__ = (
        UniqueConstraint("recipe_id", "product_id", name="uq_recipe_product"),
    )
