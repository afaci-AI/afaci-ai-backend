"""Правила единиц измерения нутриентов."""

from __future__ import annotations

from uuid import UUID

UNIT_REQUIRED = "Unit is required"
UNIT_MISMATCH = "Unit does not match nutrient name"
UNIT_REQUIRED_FOR_TYPE = "Unit is required for this nutrient type"
UNIT_CHANGE_FORBIDDEN = "Cannot change unit: nutrient name has values in another unit"


class UnitRuleViolation(Exception):
    """Нарушено правило единицы; `code` — `required` или `mismatch`."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


def nutrient_unit_for(name_unit_id: UUID | None, requested: UUID | None) -> UUID:
    """Единица значения нутриента: фиксированная единица названия.

    Если клиент передал единицу (прежние клиенты передают её всегда), она должна
    совпадать с единицей названия. У названия без фиксированной единицы
    (единицу не удалось определить по данным) её по-прежнему нужно указать.
    """
    if name_unit_id is None:
        if requested is None:
            raise UnitRuleViolation("required", UNIT_REQUIRED)
        return requested
    if requested is not None and requested != name_unit_id:
        raise UnitRuleViolation("mismatch", UNIT_MISMATCH)
    return name_unit_id
