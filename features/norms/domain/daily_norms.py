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

from collections.abc import Callable, Mapping

from features.calculator.domain.formulas import energy_kcal

PdfUrl = Callable[[str | None], str | None]

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
    norms: list[Mapping], amounts: Mapping[str, float | None] | None = None
) -> list[dict]:
    """
    Строки «нутриент — содержание — норма — доля от нормы» в порядке `NORM_ORDER`.

    `norms` — записи справочника (key, name, unit, value, source_id, basis);
    без `amounts` возвращаются только нормы (содержание и доля — None).
    """
    by_key = {norm["key"]: norm for norm in norms}
    rows = []
    for key in NORM_ORDER:
        norm = by_key.get(key)
        if norm is None:
            continue
        amount = None if amounts is None else amounts.get(key)
        value = float(norm["value"])
        rows.append(
            {
                "key": key,
                "name": norm["name"],
                "unit": norm["unit"],
                "norm": value,
                "amount": amount,
                "percent": percent_of_norm(amount, value),
                "source_id": norm.get("source_id"),
                "basis": norm.get("basis"),
            }
        )
    return rows
