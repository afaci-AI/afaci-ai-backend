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

    products = relationship("Product", back_populates="category")


class Subcategory(Base):
    __tablename__ = "subcategories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False, unique=True)

    products = relationship("Product", back_populates="subcategory")


class Region(Base):
    __tablename__ = "regions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False, unique=True)

    products = relationship("Product", back_populates="region")


class NutrientType(Base):
    __tablename__ = "nutrients_types"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False, unique=True)

    nutrients = relationship("Nutrient", back_populates="type_component")


class NutrientName(Base):
    __tablename__ = "nutrients_names"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False, unique=True)

    nutrients = relationship("Nutrient", back_populates="name_component")


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
    quantity = Column(Double, nullable=True)

    # Внешние ключи (здесь тоже нужны кавычки в ForeignKey!)
    id_product = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    id_name_component = Column(UUID(as_uuid=True), ForeignKey("nutrients_names.id"), nullable=False)
    id_type_component = Column(UUID(as_uuid=True), ForeignKey("nutrients_types.id"), nullable=False)
    unit_id = Column(UUID(as_uuid=True), ForeignKey("units.id"), nullable=False)

    # Связи
    # --- ИСПРАВЛЕНО: back_populates="nutrients" (в кавычках!) ---
    product = relationship("Product", back_populates="nutrients")
    name_component = relationship("NutrientName", back_populates="nutrients")
    type_component = relationship("NutrientType", back_populates="nutrients")
    unit = relationship("Unit", back_populates="nutrients")

    __table_args__ = (
        UniqueConstraint('id_product', 'id_name_component', name='uq_product_nutrient'),
    )
