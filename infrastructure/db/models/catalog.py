import uuid

from sqlalchemy import Column, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from .base import Base


class Category(Base):
    __tablename__ = "categories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False, unique=True)

    subcategories = relationship("Subcategory", back_populates="category")
    products = relationship("Product", back_populates="category")


class Subcategory(Base):
    __tablename__ = "subcategories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    category_id = Column(
        UUID(as_uuid=True), ForeignKey("categories.id"), nullable=False
    )
    name = Column(String, nullable=False)

    category = relationship("Category", back_populates="subcategories")
    products = relationship("Product", back_populates="subcategory")
    __table_args__ = (
        UniqueConstraint("category_id", "name", name="uq_subcategory_category_name"),
    )


class Region(Base):
    __tablename__ = "regions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False, unique=True)

    products = relationship("Product", back_populates="region")


class NutrientType(Base):
    __tablename__ = "nutrients_types"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False, unique=True)

    nutrient_names = relationship("NutrientName", back_populates="nutrient_type")


class NutrientName(Base):
    __tablename__ = "nutrients_names"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nutrient_type_id = Column(
        UUID(as_uuid=True), ForeignKey("nutrients_types.id"), nullable=False
    )
    name = Column(String, nullable=False)

    nutrient_type = relationship("NutrientType", back_populates="nutrient_names")
    nutrients = relationship("Nutrient", back_populates="name_component")
    __table_args__ = (
        UniqueConstraint("nutrient_type_id", "name", name="uq_nutrient_name_type_name"),
    )


class Unit(Base):
    __tablename__ = "units"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False, unique=True)

    nutrients = relationship("Nutrient", back_populates="unit")
