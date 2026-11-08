"""
Фиксированные единицы измерения нутриентов.

Единица принадлежит названию нутриента (`nutrients_names.unit_id`), а не
вводится при добавлении значения к продукту. Для нового названия единица
определяется типом состава; для типа без правила её нужно указать явно.

Соответствие проверено по данным БД: у каждого названия нутриента ровно одна
единица, внутри типа состава расхождений нет. Числа при смене единицы
не пересчитываются: преобразование единиц допускается только на backend.
"""

CHEMICAL_TYPE = "Химический состав"
AMINO_ACID_TYPE = "Аминокислотный состав"
MINERAL_TYPE = "Минеральный состав"

PERCENT_PER_100G = "%/100г"
MG_PER_100G = "мг/100г"

DEFAULT_UNIT_BY_TYPE: dict[str, str] = {
    CHEMICAL_TYPE: PERCENT_PER_100G,
    AMINO_ACID_TYPE: MG_PER_100G,
    MINERAL_TYPE: MG_PER_100G,
}


def default_unit_name(type_name: str | None) -> str | None:
    """Название единицы по умолчанию для типа состава или None, если правила нет."""
    if not type_name:
        return None
    return DEFAULT_UNIT_BY_TYPE.get(type_name)
