"""
Класс нутриента: макросостав, микросостав, аминокислоты или прочее.

Класс принадлежит названию нутриента (`nutrients_names.nutrient_class`), а не
типу состава: «Химический состав» неоднороден (белок, жир, углеводы и волокна —
макро, влага и зольность — прочее). Тип остаётся подзаголовком внутри класса.
Для нового названия класс по умолчанию берётся из типа состава.
"""

from .nutrient_units import AMINO_ACID_TYPE, CHEMICAL_TYPE, MINERAL_TYPE

MACRO = "macro"
MICRO = "micro"
AMINO = "amino"
OTHER = "other"

NUTRIENT_CLASSES = (MACRO, MICRO, AMINO, OTHER)

DEFAULT_CLASS_BY_TYPE: dict[str, str] = {
    CHEMICAL_TYPE: OTHER,
    AMINO_ACID_TYPE: AMINO,
    MINERAL_TYPE: MICRO,
}

# Названия химического состава, относящиеся к макросоставу.
MACRO_NAMES = (
    "Массовая доля белка",
    "Массовая доля жира",
    "Углеводы",
    "Пищевые волокна",
)


def default_nutrient_class(type_name: str | None) -> str:
    """Класс по умолчанию для типа состава; без правила — «прочее»."""
    return DEFAULT_CLASS_BY_TYPE.get(type_name or "", OTHER)
