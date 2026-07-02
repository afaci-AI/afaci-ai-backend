import uuid
from sqlalchemy import Column, String, ForeignKey, Double, Integer, Boolean, DateTime, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from .base import Base, _utcnow


class User(Base):
    """Пользователь приложения (аутентификация по email + пароль)."""
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, nullable=False, unique=True)
    name = Column(String, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, nullable=False, default="viewer")
    is_active = Column(Boolean, nullable=False, default=True)
    access_expires_at = Column(DateTime(timezone=True), nullable=True)
    must_change_password = Column(Boolean, nullable=False, default=False)
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
    """Сохранённая пользователем рецептура с кэшем метрик качества."""
    __tablename__ = "saved_recipes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    group_id = Column(UUID(as_uuid=True), ForeignKey("recipe_groups.id", ondelete="SET NULL"), nullable=True)
    name = Column(String, nullable=False)
    reference_protein_id = Column(UUID(as_uuid=True), ForeignKey("reference_proteins.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)

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

    price_per_kg = Column(Double, nullable=True)

    saved_recipe = relationship("SavedRecipe", back_populates="items")
    product = relationship("Product")
