import uuid
from sqlalchemy import Column, String, ForeignKey, Double, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, DeclarativeBase


class Base(DeclarativeBase):
    pass


# --- СПРАВОЧНИКИ (Родительские таблицы) ---

class Category(Base):
    __tablename__ = "categories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False, unique=True)

    subcategories = relationship("Subcategory", back_populates="category")
    products = relationship("Product", back_populates="category")


class Subcategory(Base):
    __tablename__ = "subcategories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    category_id = Column(UUID(as_uuid=True), ForeignKey("categories.id"), nullable=False)
    name = Column(String, nullable=False)

    category = relationship("Category", back_populates="subcategories")
    products = relationship("Product", back_populates="subcategory")
    __table_args__ = (UniqueConstraint('category_id', 'name', name='uq_subcategory_category_name'),)


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
    nutrient_type_id = Column(UUID(as_uuid=True), ForeignKey("nutrients_types.id"), nullable=False)
    name = Column(String, nullable=False)

    nutrient_type = relationship("NutrientType", back_populates="nutrient_names")
    nutrients = relationship("Nutrient", back_populates="name_component")
    __table_args__ = (UniqueConstraint('nutrient_type_id', 'name', name='uq_nutrient_name_type_name'),)


class Unit(Base):
    __tablename__ = "units"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False, unique=True)

    nutrients = relationship("Nutrient", back_populates="unit")


# --- ОСНОВНЫЕ ТАБЛИЦЫ ДАННЫХ ---

class Product(Base):
    __tablename__ = "products"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)

    # Внешние ключи
    category_id = Column(UUID(as_uuid=True), ForeignKey("categories.id"), nullable=False)
    subcategory_id = Column(UUID(as_uuid=True), ForeignKey("subcategories.id"), nullable=True)
    region_id = Column(UUID(as_uuid=True), ForeignKey("regions.id"), nullable=False)

    # Связи
    category = relationship("Category", back_populates="products")
    subcategory = relationship("Subcategory", back_populates="products")
    region = relationship("Region", back_populates="products")

    # --- ИСПРАВЛЕНО: back_populates="product" (в кавычках!) ---
    # Добавляем ограничение уникальности
    __table_args__ = (UniqueConstraint('name', 'region_id', name='uq_product_name_region'),)
    nutrients = relationship("Nutrient", back_populates="product", cascade="all, delete-orphan")


class Nutrient(Base):
    __tablename__ = "nutrients"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    quantity = Column(Double, nullable=False)

    # Внешние ключи
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    nutrient_name_id = Column(UUID(as_uuid=True), ForeignKey("nutrients_names.id"), nullable=False)
    unit_id = Column(UUID(as_uuid=True), ForeignKey("units.id"), nullable=False)

    # Связи
    product = relationship("Product", back_populates="nutrients")
    name_component = relationship("NutrientName", back_populates="nutrients")
    unit = relationship("Unit", back_populates="nutrients")

    __table_args__ = (
        UniqueConstraint('product_id', 'nutrient_name_id', name='uq_product_nutrient'),
    )
