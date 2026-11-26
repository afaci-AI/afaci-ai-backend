"""Сборка отчётов: выборка, расчёт ккал по формуле калькулятора, подготовка таблиц."""

from __future__ import annotations

from datetime import datetime

from core.errors import BadRequestError, NotFoundError
from features.calculator.domain.formulas.macro import energy_kcal

from .models import (
    MAX_LIST_ROWS,
    MAX_TOP,
    ListCriteria,
    RankingCriteria,
    ReportDocument,
    ReportSection,
    ReportTable,
)
from .nutrition import recipe_nutrition
from .ports import ReportQueries

GROUP_ORDER = ["Химический состав", "Аминокислотный состав", "Минеральный состав"]
MISSING = "—"
LOOKUP_LIMIT = 20
TRUNCATED_NOTE = f"Показаны первые {MAX_LIST_ROWS} строк: уточните критерии, чтобы увидеть остальное."
KCAL_NOTE = "Ккал = 4·белок + 9·жир + 4·углеводы; «—», если хотя бы одного показателя нет в базе."


def clean(value: str | None) -> str | None:
    value = (value or "").strip()
    return value or None


def fmt(value: float | None) -> str:
    """Число с запятой: до 4 знаков, без хвостовых нулей; очень малые — в экспоненте."""
    if value is None:
        return MISSING
    text = f"{value:.4f}".rstrip("0").rstrip(".")
    if text in {"0", "-0"} and value != 0:
        text = f"{value:.2e}"
    return text.replace(".", ",")


class ReportService:
    def __init__(self, queries: ReportQueries) -> None:
        self._q = queries

    async def options(self) -> dict:
        return await self._q.options()

    async def lookup(self, name: str | None) -> list[dict]:
        name = clean(name)
        if name is None:
            return []
        return await self._q.lookup_products(name, LOOKUP_LIMIT)

    async def recipes(self, user_id: str) -> list[dict]:
        return await self._q.user_recipes(user_id)

    async def nutrition_report(
        self, recipe_id: str, user_id: str, author: str, now: datetime
    ) -> ReportDocument:
        recipe = await self._q.saved_recipe(recipe_id, user_id)
        if recipe is None:
            raise NotFoundError("Рецептура не найдена.")
        items = await self._q.recipe_items(recipe_id)
        reference = await self._q.reference(recipe["reference_id"])
        result = recipe_nutrition(items, reference)
        doc = ReportDocument(
            title=f"Пищевая ценность рецептуры: {recipe['name']}",
            author=author,
            created_at=now,
            criteria=[
                ("Рецептура", recipe["name"]),
                ("Эталон белка", reference["name"]),
                ("Масса рецептуры, г", fmt(result.mass_g)),
            ],
            filename="recipe-nutrition.pdf",
        )
        doc.sections.append(
            ReportSection(
                "Состав рецептуры",
                ReportTable(
                    columns=["Ингредиент", "Масса, г"],
                    rows=[[it["name"], fmt(it["amount_g"])] for it in items],
                    widths=[75, 25],
                    align=["L", "R"],
                ),
            )
        )
        doc.sections.append(
            ReportSection(
                "Пищевая ценность на 100 г",
                ReportTable(
                    columns=["Показатель", "Значение", "Единица"],
                    rows=[
                        ["Белок", fmt(result.protein), "г"],
                        ["Жир", fmt(result.fat), "г"],
                        ["Углеводы", fmt(result.carb), "г"],
                        ["Энергоценность", fmt(result.energy_kcal), "ккал"],
                    ],
                    widths=[50, 25, 25],
                    align=["L", "R", "L"],
                ),
            )
        )
        if result.scores:
            doc.sections.append(
                ReportSection(
                    "Аминокислотный скор",
                    ReportTable(
                        columns=["Группа НАК", "Скор, %"],
                        rows=[[s.name, fmt(s.score)] for s in result.scores],
                        widths=[60, 40],
                        align=["L", "R"],
                    ),
                )
            )
        if result.limiting is not None:
            doc.notes.append(
                f"Лимитирующая аминокислота: {result.limiting.name}, "
                f"скор {fmt(result.limiting.score)} %."
            )
        else:
            doc.notes.append("Скор не рассчитан: нет данных по аминокислотам.")
        doc.notes.append(KCAL_NOTE)
        return doc

    async def products_report(
        self, criteria: ListCriteria, author: str, now: datetime
    ) -> ReportDocument:
        criteria = ListCriteria(
            category=clean(criteria.category),
            subcategory=clean(criteria.subcategory),
            region=clean(criteria.region),
            name=clean(criteria.name),
        )
        rows = await self._q.products(criteria, MAX_LIST_ROWS + 1)
        truncated = len(rows) > MAX_LIST_ROWS
        rows = rows[:MAX_LIST_ROWS]
        doc = ReportDocument(
            title="Перечень сырья",
            author=author,
            created_at=now,
            criteria=[
                ("Категория", criteria.category or "любая"),
                ("Подкатегория", criteria.subcategory or "любая"),
                ("Регион", criteria.region or "любой"),
                ("Название содержит", criteria.name or "—"),
            ],
            filename="products-list.pdf",
        )
        if not rows:
            doc.empty_message = "Нет данных: под критерии ничего не подошло."
            return doc
        table_rows = []
        for i, r in enumerate(rows, 1):
            kcal = energy_kcal(r["protein"], r["fat"], r["carb"])
            table_rows.append(
                [
                    str(i),
                    r["name"],
                    r["region"],
                    fmt(r["protein"]),
                    fmt(r["fat"]),
                    fmt(r["carb"]),
                    fmt(kcal),
                ]
            )
        doc.sections.append(
            ReportSection(
                None,
                ReportTable(
                    columns=[
                        "№",
                        "Название",
                        "Регион",
                        "Белок, г/100 г",
                        "Жир, г/100 г",
                        "Углев., г/100 г",
                        "Ккал/ 100 г",
                    ],
                    rows=table_rows,
                    widths=[5, 33, 19, 11, 11, 11, 12],
                    align=["R", "L", "L", "R", "R", "R", "R"],
                ),
            )
        )
        doc.notes.append(f"Найдено строк: {len(rows)}.")
        doc.notes.append(KCAL_NOTE)
        if truncated:
            doc.notes.append(TRUNCATED_NOTE)
        return doc

    async def ranking_report(
        self, criteria: RankingCriteria, author: str, now: datetime
    ) -> ReportDocument:
        nutrient = clean(criteria.nutrient)
        if nutrient is None:
            raise BadRequestError("Укажите нутриент.")
        if not 1 <= criteria.top <= MAX_TOP:
            raise BadRequestError(f"N должно быть от 1 до {MAX_TOP}.")
        unit = await self._q.nutrient_unit(nutrient)
        if unit is None:
            raise BadRequestError(f"Нутриент «{nutrient}» не найден.")
        criteria = RankingCriteria(
            nutrient=nutrient,
            order=criteria.order,
            top=criteria.top,
            category=clean(criteria.category),
        )
        rows = await self._q.ranking(criteria)
        doc = ReportDocument(
            title=f"Рейтинг сырья: {nutrient}",
            author=author,
            created_at=now,
            criteria=[
                ("Нутриент", f"{nutrient}, {unit}"),
                (
                    "Порядок",
                    "по убыванию" if criteria.order == "desc" else "по возрастанию",
                ),
                ("Количество (N)", str(criteria.top)),
                ("Категория", criteria.category or "любая"),
            ],
            filename="products-ranking.pdf",
        )
        if not rows:
            doc.empty_message = "Нет данных: под критерии ничего не подошло."
            return doc
        doc.sections.append(
            ReportSection(
                None,
                ReportTable(
                    columns=[
                        "Место",
                        "Название",
                        "Категория",
                        "Регион",
                        f"Значение, {unit}",
                        "Погрешность",
                    ],
                    rows=[
                        [
                            str(i),
                            r["name"],
                            r["category"],
                            r["region"],
                            fmt(r["quantity"]),
                            fmt(r["error_rate"]),
                        ]
                        for i, r in enumerate(rows, 1)
                    ],
                    widths=[7, 27, 19, 17, 15, 15],
                    align=["R", "L", "L", "L", "R", "R"],
                ),
            )
        )
        doc.notes.append(f"Показано строк: {len(rows)}.")
        return doc

    async def card_report(
        self, product_id: str, author: str, now: datetime
    ) -> ReportDocument:
        product = await self._q.product(product_id)
        if product is None:
            raise NotFoundError("Продукт не найден.")
        nutrients = await self._q.product_nutrients(product_id)
        doc = ReportDocument(
            title=f"Карточка сырья: {product['name']}",
            author=author,
            created_at=now,
            criteria=[
                ("Категория", product["category"]),
                ("Подкатегория", product["subcategory"] or "—"),
                ("Регион", product["region"]),
            ],
            filename="product-card.pdf",
        )
        if not nutrients:
            doc.empty_message = "Нет данных: у продукта нет нутриентов."
            return doc
        groups: dict[str, list[dict]] = {}
        for n in nutrients:
            groups.setdefault(n["type"], []).append(n)
        order = sorted(
            groups,
            key=lambda t: (
                GROUP_ORDER.index(t) if t in GROUP_ORDER else len(GROUP_ORDER),
                t,
            ),
        )
        for group in order:
            doc.sections.append(
                ReportSection(
                    group,
                    ReportTable(
                        columns=["Показатель", "Значение", "Единица", "Погрешность"],
                        rows=[
                            [
                                n["name"],
                                fmt(n["quantity"]),
                                n["unit"],
                                fmt(n["error_rate"]),
                            ]
                            for n in groups[group]
                        ],
                        widths=[44, 18, 20, 18],
                        align=["L", "R", "L", "R"],
                    ),
                )
            )
        return doc
