"""Описание простых справочников: названия, сообщения, правила показа.

Категории, регионы, единицы и типы нутриентов устроены одинаково (имя + CRUD),
поэтому описываются данными, а не отдельным кодом на каждый справочник.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class DictionarySpec:
    kind: str  # ключ модели в хранилище
    path: str  # путь в API: /categories
    tag: str  # тег OpenAPI
    singular: str  # api_create_<singular>
    plural: str  # api_list_<plural>
    model_name: str  # «Category already exists», «Category not found»
    label: str  # «Category with this name already exists»
    delete_label: str  # «Cannot delete <delete_label>: <delete_reason>»
    delete_reason: str
    searchable: bool = False  # список с фильтром ?name=

    @property
    def duplicate_message(self) -> str:
        return f"{self.model_name} already exists"

    @property
    def not_found_message(self) -> str:
        return f"{self.model_name} not found"

    @property
    def same_name_message(self) -> str:
        return f"{self.label} with this name already exists"

    @property
    def in_use_message(self) -> str:
        return f"Cannot delete {self.delete_label}: {self.delete_reason}"


CATEGORIES = DictionarySpec(
    kind="category",
    path="/categories",
    tag="Categories",
    singular="category",
    plural="categories",
    model_name="Category",
    label="Category",
    delete_label="category",
    delete_reason="used in products",
    searchable=True,
)
REGIONS = DictionarySpec(
    kind="region",
    path="/regions",
    tag="Regions",
    singular="region",
    plural="regions",
    model_name="Region",
    label="Region",
    delete_label="region",
    delete_reason="used in products",
)
UNITS = DictionarySpec(
    kind="unit",
    path="/units",
    tag="Units",
    singular="unit",
    plural="units",
    model_name="Unit",
    label="Unit",
    delete_label="unit",
    delete_reason="used in nutrients",
)
NUTRIENT_TYPES = DictionarySpec(
    kind="nutrient_type",
    path="/nutrient-types",
    tag="Nutrient Types",
    singular="nutrient_type",
    plural="nutrient_types",
    model_name="NutrientType",
    label="Nutrient type",
    delete_label="nutrient type",
    delete_reason="used in nutrient names",
)

# Справочники с родителем или единицей: создание и изменение — отдельные сценарии,
# а список, чтение, удаление и массовое добавление имён общие.
SUBCATEGORIES = DictionarySpec(
    kind="subcategory",
    path="/subcategories",
    tag="Subcategories",
    singular="subcategory",
    plural="subcategories",
    model_name="Subcategory",
    label="Subcategory",
    delete_label="subcategory",
    delete_reason="used in products",
)
NUTRIENT_NAMES = DictionarySpec(
    kind="nutrient_name",
    path="/nutrient-names",
    tag="Nutrient Names",
    singular="nutrient_name",
    plural="nutrient_names",
    model_name="NutrientName",
    label="Nutrient name",
    delete_label="nutrient name",
    delete_reason="used in nutrients",
)

SIMPLE_DICTIONARIES = (CATEGORIES, REGIONS, UNITS, NUTRIENT_TYPES)
SUBCATEGORY_KIND = SUBCATEGORIES.kind
NUTRIENT_NAME_KIND = NUTRIENT_NAMES.kind
