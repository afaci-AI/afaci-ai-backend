import uuid
from sqlalchemy import Column, String, ForeignKey, Double, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from .base import Base


class Product(Base):
    __tablename__ = "products"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)

    category_id = Column(UUID(as_uuid=True), ForeignKey("categories.id"), nullable=False)
    subcategory_id = Column(UUID(as_uuid=True), ForeignKey("subcategories.id"), nullable=True)
    region_id = Column(UUID(as_uuid=True), ForeignKey("regions.id"), nullable=False)

    category = relationship("Category", back_populates="products")
    subcategory = relationship("Subcategory", back_populates="products")
    region = relationship("Region", back_populates="products")
    nutrients = relationship("Nutrient", back_populates="product", cascade="all, delete-orphan")

    __table_args__ = (UniqueConstraint('name', 'region_id', name='uq_product_name_region'),)


class Nutrient(Base):
    __tablename__ = "nutrients"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    quantity = Column(Double, nullable=False)
    error_rate = Column(Double, nullable=True)

    product_id = Column('id_product', UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    nutrient_name_id = Column('id_name_component', UUID(as_uuid=True), ForeignKey("nutrients_names.id"), nullable=False)
    nutrient_type_id = Column('id_type_component', UUID(as_uuid=True), ForeignKey("nutrients_types.id"), nullable=True)
    unit_id = Column(UUID(as_uuid=True), ForeignKey("units.id"), nullable=False)

    product = relationship("Product", back_populates="nutrients")
    name_component = relationship("NutrientName", back_populates="nutrients")
    unit = relationship("Unit", back_populates="nutrients")

    __table_args__ = (
        UniqueConstraint('id_product', 'id_name_component', name='uq_product_nutrient'),
    )
