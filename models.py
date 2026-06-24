import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, ForeignKey, Double, Integer, Boolean, Text,
    UniqueConstraint, DateTime,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, DeclarativeBase


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)

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
    error_rate = Column(Double, nullable=True)

    # Python-атрибут → реальное имя колонки в БД
    product_id = Column('id_product', UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    nutrient_name_id = Column('id_name_component', UUID(as_uuid=True), ForeignKey("nutrients_names.id"), nullable=False)
    nutrient_type_id = Column('id_type_component', UUID(as_uuid=True), ForeignKey("nutrients_types.id"), nullable=True)
    unit_id = Column(UUID(as_uuid=True), ForeignKey("units.id"), nullable=False)

    # Связи
    product = relationship("Product", back_populates="nutrients")
    name_component = relationship("NutrientName", back_populates="nutrients")
    unit = relationship("Unit", back_populates="nutrients")

    __table_args__ = (
        UniqueConstraint('id_product', 'id_name_component', name='uq_product_nutrient'),
    )


# --- КАЛЬКУЛЯТОР: эталонные белки и рецептуры ---

class ReferenceProtein(Base):
    """Эталонный (идеальный) белок ФАО/ВОЗ — шкала для аминокислотного скора."""
    __tablename__ = "reference_proteins"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False, unique=True)
    year = Column(Integer, nullable=True)
    is_default = Column(Boolean, nullable=False, default=False)
    description = Column(Text, nullable=True)

    values = relationship("ReferenceProteinValue", back_populates="reference_protein",
                          cascade="all, delete-orphan")


class ReferenceProteinValue(Base):
    """Значение НАК эталона, г/100 г белка (группы: ИЗО, ЛЕЙ, ВАЛ, МЕТ+ЦИС, Ф+Т, ТРИ, ТРЕ, ЛИЗ)."""
    __tablename__ = "reference_protein_values"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    reference_protein_id = Column(UUID(as_uuid=True), ForeignKey("reference_proteins.id"), nullable=False)
    amino_acid = Column(String, nullable=False)
    value = Column(Double, nullable=False)
    sort_order = Column(Integer, nullable=False, default=0)

    reference_protein = relationship("ReferenceProtein", back_populates="values")
    __table_args__ = (UniqueConstraint('reference_protein_id', 'amino_acid', name='uq_refprotein_amino'),)


class Recipe(Base):
    """Рецептура (контроль/опытный). База — 100 г: масса в граммах = доле Xᵢ, %."""
    __tablename__ = "recipes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False, unique=True)
    description = Column(Text, nullable=True)
    sample_type = Column(String, nullable=False, default="контроль")

    items = relationship("RecipeItem", back_populates="recipe", cascade="all, delete-orphan")


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
    __table_args__ = (UniqueConstraint('recipe_id', 'product_id', name='uq_recipe_product'),)


# --- ПОЛЬЗОВАТЕЛИ И СОХРАНЁННЫЕ РЕЦЕПТУРЫ ---

class User(Base):
    """Пользователь приложения (аутентификация по email + пароль)."""
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, nullable=False, unique=True)
    name = Column(String, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, nullable=False, default="viewer")
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    last_login_at = Column(DateTime(timezone=True), nullable=True)

    groups = relationship("RecipeGroup", back_populates="user", cascade="all, delete-orphan")
    saved_recipes = relationship("SavedRecipe", back_populates="user", cascade="all, delete-orphan")


class RecipeGroup(Base):
    """Группа сохранённых рецептур пользователя (как плейлист)."""
    __tablename__ = "recipe_groups"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

    user = relationship("User", back_populates="groups")
    saved_recipes = relationship("SavedRecipe", back_populates="group")


class SavedRecipe(Base):
    """Сохранённая пользователем рецептура. Имя НЕ обязано быть уникальным.

    Метрики качества (БЦ, КРАС, V, G и др.) кэшируются при сохранении/правке —
    для списков и ранжирования рецептур без повторного расчёта.
    """
    __tablename__ = "saved_recipes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    group_id = Column(UUID(as_uuid=True), ForeignKey("recipe_groups.id", ondelete="SET NULL"), nullable=True)
    name = Column(String, nullable=False)
    reference_protein_id = Column(UUID(as_uuid=True), ForeignKey("reference_proteins.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)

    # кэш показателей
    bc = Column(Double, nullable=True)
    kras = Column(Double, nullable=True)
    v_coef = Column(Double, nullable=True)
    g_coef = Column(Double, nullable=True)
    energy_kcal = Column(Double, nullable=True)
    c_min_name = Column(String, nullable=True)
    c_min_score = Column(Double, nullable=True)

    user = relationship("User", back_populates="saved_recipes")
    group = relationship("RecipeGroup", back_populates="saved_recipes")
    items = relationship("SavedRecipeItem", back_populates="saved_recipe",
                         cascade="all, delete-orphan")


class SavedRecipeItem(Base):
    """Ингредиент сохранённой рецептуры: продукт + Xᵢ (граммы на 100 г)."""
    __tablename__ = "saved_recipe_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    saved_recipe_id = Column(UUID(as_uuid=True), ForeignKey("saved_recipes.id", ondelete="CASCADE"), nullable=False)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    amount_g = Column(Double, nullable=False)
    sort_order = Column(Integer, nullable=False, default=0)

    saved_recipe = relationship("SavedRecipe", back_populates="items")
    product = relationship("Product")
