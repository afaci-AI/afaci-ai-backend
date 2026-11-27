"""
Суточные нормы и доля от нормы.

Чистая логика без БД: энергия по белкам, жирам и углеводам, доля от нормы,
сборка строк для клиентов. Значения норм и источники лежат в БД (`daily_norms`,
`sources`) и вносятся миграцией; клиенты ничего не считают сами.

Норма — одна усреднённая величина для взрослых 18–64 лет, а не норма конкретного
человека: в МР 2.3.1.0253-21 значения заданы по полу, возрасту и группе физической
активности, усреднение описано в `basis` каждой нормы и в тексте `NORMS_INFO`.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace

from features.calculator.domain.formulas import energy_kcal

from .records import CompositionEntry, DailyNorm, NormRow

NORM_ORDER = ("energy", "protein", "fat", "carbs", "fiber")

# Названия нутриентов продукта в БД (тип «Химический состав», единица %/100г = г/100 г).
PRODUCT_NUTRIENT_BY_KEY = {
    "protein": "Массовая доля белка",
    "fat": "Массовая доля жира",
    "carbs": "Углеводы",
    "fiber": "Пищевые волокна",
}

NORMS_INFO = {
    "title": "Суточные нормы",
    "paragraphs": [
        (
            "Нормы взяты из методических рекомендаций МР 2.3.1.0253-21 «Нормы "
            "физиологических потребностей в энергии и пищевых веществах для различных "
            "групп населения Российской Федерации» (Роспотребнадзор, 2021)."
        ),
        (
            "В документе нормы заданы отдельно для мужчин и женщин, трёх возрастов "
            "взрослых (18–29, 30–44, 45–64 года) и четырёх групп физической активности: "
            "энергия от 1700 до 3800 ккал в сутки. Единой нормы для всех в документе нет, "
            "поэтому в программе выбрана одна усреднённая величина — среднее арифметическое "
            "по всем 24 группам взрослых (таблицы 9 и 14), округлённое до целого. Выбор группы "
            "пользователем не предусмотрен."
        ),
        (
            "Пищевые волокна: в документе для взрослых указан диапазон 20–25 г в сутки; "
            "принята его верхняя граница."
        ),
        (
            "Энергетическая ценность считается по белкам, жирам и углеводам с "
            "коэффициентами 4, 9 и 4 ккал на 1 г (приложение 3 к МР 2.3.1.0253-21)."
        ),
        (
            "Минеральные вещества: нормы для взрослых старше 18 лет из таблиц 12 и 17 "
            "(мужчины и женщины). Где нормы различаются, принято среднее, округлённое до "
            "целого: железо 14 мг (10 и 18 мг), селен 63 мкг (70 и 55 мкг). Кальций — "
            "1000 мг, норма взрослых до 64 лет (старше 65 лет — 1200 мг). Для кобальта и "
            "ванадия в документе даны адекватные уровни потребления (таблицы 13 и 18), а не "
            "физиологические нормы; они отмечены в таблице. Для алюминия, бора, лития, "
            "никеля и олова норм нет: показывается только содержание."
        ),
        (
            "Селен, йод, хром, кобальт и ванадий показаны в микрограммах, как в документе; "
            "в базе значения хранятся в миллиграммах и пересчитываются (1 мг = 1000 мкг)."
        ),
        (
            "Доля от нормы = содержание на 100 г продукта (или рецептуры) ÷ усреднённая "
            "суточная норма × 100 %."
        ),
    ],
    "disclaimer": (
        "Усреднённая норма — ориентир, а не рекомендация для конкретного человека. "
        "Реальная потребность зависит от пола, возраста, массы тела и физической "
        "активности и может заметно отличаться; программа не заменяет консультацию "
        "специалиста."
    ),
}


def percent_of_norm(amount: float | None, norm: float) -> float | None:
    """Доля от нормы, %, округлённая до десятых; None, если значения нет."""
    if amount is None or norm <= 0:
        return None
    return round(amount / norm * 100, 1)


def amounts_from_macros(
    protein: float | None,
    fat: float | None,
    carb: float | None,
    fiber: float | None,
    energy: float | None = None,
) -> dict[str, float | None]:
    """Содержание на 100 г по ключам норм; энергия считается, если не передана."""
    return {
        "energy": energy if energy is not None else energy_kcal(protein, fat, carb),
        "protein": protein,
        "fat": fat,
        "carbs": carb,
        "fiber": fiber,
    }


def build_norm_rows(
    norms: list[DailyNorm], amounts: Mapping[str, float | None] | None = None
) -> list[NormRow]:
    """
    Строки «нутриент — содержание — норма — доля от нормы» в порядке `NORM_ORDER`.

    Без `amounts` возвращаются только нормы (содержание и доля — None).
    """
    by_key = {norm.key: norm for norm in norms}
    rows = []
    for key in NORM_ORDER:
        norm = by_key.get(key)
        if norm is None:
            continue
        amount = None if amounts is None else amounts.get(key)
        rows.append(
            NormRow(
                key=key,
                name=norm.name,
                unit=norm.unit,
                norm=norm.value,
                amount=amount,
                percent=percent_of_norm(amount, norm.value),
                source_id=norm.source_id,
                basis=norm.basis,
                kind=norm.kind,
            )
        )
    return rows


# Единственное место перевода единиц: значение продукта (мг/100 г) → единица нормы.
UNIT_FACTORS: dict[tuple[str, str], float] = {
    ("мг", "мкг"): 1000.0,
    ("мкг", "мг"): 0.001,
}


def convert_amount(
    amount: float | None, from_unit: str | None, to_unit: str
) -> float | None:
    """Значение в единице нормы; единицы без правила перевода не смешиваются."""
    if amount is None or from_unit == to_unit:
        return amount
    factor = UNIT_FACTORS.get((from_unit or "", to_unit))
    if factor is None:
        raise ValueError(f"Нет перевода единиц {from_unit!r} → {to_unit!r}")
    return amount * factor


def short_unit(unit: str | None) -> str | None:
    """Единица для показа: «мг/100г» → «мг» (все значения даны на 100 г)."""
    return None if unit is None else unit.split("/")[0]


def _class_row(entry: CompositionEntry, norm: DailyNorm | None) -> NormRow:
    unit = short_unit(entry.unit)
    row = NormRow(
        key=entry.name,
        name=entry.name,
        unit=unit,
        amount=entry.amount,
        partial=entry.partial,
    )
    if norm is None:
        return row
    try:
        amount = convert_amount(entry.amount, unit, norm.unit)
    except ValueError:
        # У нутриента в справочнике нет единицы или её нельзя перевести в
        # единицу нормы: долю не считаем, чтобы не показать неверный процент,
        # но и расчёт рецептуры не роняем.
        return row
    return replace(
        row,
        unit=norm.unit,
        norm=norm.value,
        amount=amount,
        percent=percent_of_norm(amount, norm.value),
        kind=norm.kind,
        source_id=norm.source_id,
        basis=norm.basis,
    )


def build_class_rows(
    entries: list[CompositionEntry], norms: list[DailyNorm] | None = None
) -> list[NormRow]:
    """
    Строки микросостава и прочих показателей.

    Если для нутриента есть норма (ключ нормы — название нутриента), значение
    переводится в единицу нормы и считается доля; иначе `norm` и `percent` — None.
    """
    by_key = {norm.key: norm for norm in norms or []}
    return [_class_row(entry, by_key.get(entry.name)) for entry in entries]


def mineral_norm_rows(norms: list[DailyNorm]) -> list[NormRow]:
    """Нормы минералов без содержания — для общего списка норм."""
    return build_class_rows(
        [
            CompositionEntry(name=norm.key, unit=norm.unit, amount=None)
            for norm in norms
            if norm.key not in NORM_ORDER
        ],
        norms,
    )
