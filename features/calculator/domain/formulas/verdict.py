"""Заключение о белке строго по выбранному эталону ФАО/ВОЗ — без условных порогов.

Критерий один: белок полноценен по эталону, если содержание каждой из 8 групп
НАК не ниже эталона (скор ≥ 100 %). Иначе перечисляются НАК ниже эталона с их
скором и недостачей в г/100 г белка. КРАС, БЦ, U и G выводятся числами, без
оценочных слов. Усвояемость белка не учитывается.
"""

from __future__ import annotations

from .quality import Quality

EXPERIMENTAL_NOTE = (
    "Экспериментальная функция. Заключение строится только по аминокислотному "
    "составу белка в сравнении с выбранным эталоном ФАО/ВОЗ; усвояемость и другие "
    "факторы не учитываются."
)

CRITERION = (
    "Внутреннее правило программы: белок полноценен по эталону, если "
    "аминокислотный скор каждой из 8 групп НАК не ниже 100 %. "
    "Значения эталона взяты из источника, указанного ниже."
)


def fmt(value: float, digits: int = 1) -> str:
    """Число с десятичной запятой для текста заключения."""
    return f"{value:.{digits}f}".replace(".", ",")


def _deficits(scored: list[dict]) -> list[dict]:
    return sorted(
        (
            {
                "name": r["name"],
                "score": round(r["score"], 1),
                "m_j": round(r["m_j"], 2),
                "reference": r["reference"],
                "deficit": round(r["reference"] - r["m_j"], 2),
            }
            for r in scored
            if r["score"] < 100
        ),
        key=lambda d: d["score"],
    )


def _limitations(missing_amino: list[str], amino_coverage: float | None) -> list[str]:
    if not missing_amino:
        return []
    share = (
        f" Данные по аминокислотам есть у {fmt(amino_coverage * 100, 0)} % белка "
        f"рецептуры."
        if amino_coverage is not None
        else ""
    )
    return [
        "Нет данных об аминокислотном составе у белоксодержащих ингредиентов: "
        + ", ".join(missing_amino)
        + "."
        + share
        + " Они не учтены в расчёте скоров."
    ]


def _group_points(
    scored: list[dict], deficits: list[dict], missing_amino: list[str]
) -> list[str]:
    if not deficits:
        return [
            f"Все {len(scored)} групп незаменимых аминокислот не ниже эталона "
            f"(аминокислотный скор ≥ 100 %)"
            + (
                " — для учтённой части белка; полноценность всей рецептуры не подтверждена."
                if missing_amino
                else ": по эталону белок полноценный."
            )
        ]
    lowest = deficits[0]
    points = [
        (
            f"Ниже эталона {len(deficits)} из {len(scored)} групп незаменимых "
            f"аминокислот. Лимитирующая — {lowest['name']}: скор "
            f"{fmt(lowest['score'])} %."
        )
    ]
    points.extend(
        f"{d['name']}: скор {fmt(d['score'])} % — {fmt(d['m_j'], 2)} г против "
        f"{fmt(d['reference'], 2)} г на 100 г белка, недостаёт "
        f"{fmt(d['deficit'], 2)} г."
        for d in deficits
    )
    return points


def _level(complete: bool, confirmed: bool, ref_name: str) -> tuple[str, str]:
    if confirmed:
        return "complete", f"Белок полноценный по эталону {ref_name}"
    if complete:
        return (
            "unconfirmed",
            f"Полноценность по эталону {ref_name} не подтверждена: мало данных",
        )
    return "incomplete", f"Белок неполноценный по эталону {ref_name}"


def build_verdict(
    amino_rows: list[dict],
    reference: dict,
    quality: Quality,
    missing_amino: list[str] | None = None,
    amino_coverage: float | None = None,
) -> dict | None:
    """{level, headline, points[], reference, deficits[], ...} или None,
    если расчёт скоров невозможен. Без обращения к банку продуктов."""
    scored = [r for r in amino_rows if r["score"] is not None]
    if not scored or quality.kras is None or quality.bc is None:
        return None

    ref_name = reference["name"]
    deficits = _deficits(scored)
    missing_amino = missing_amino or []
    limitations = _limitations(missing_amino, amino_coverage)
    complete = not deficits
    # Без части данных «полноценный» не подтверждён; недостачи по известной части
    # остаются верными как минимум для неё.
    confirmed = complete and not missing_amino

    points: list[str] = [
        (
            f"Оценка выполнена по эталону «{ref_name}»: содержание каждой группы "
            f"незаменимых аминокислот в белке рецептуры сравнивается со значением "
            f"эталона (г на 100 г белка). Усвояемость белка не учитывается."
        )
    ]
    points.extend(limitations)
    points.extend(_group_points(scored, deficits, missing_amino))
    points.append(
        f"Расчётные показатели: КРАС = {fmt(quality.kras)} %, БЦ = {fmt(quality.bc)} %."
    )
    if quality.util_u is not None and quality.util_g is not None:
        points.append(
            f"Справочно: коэффициент утилитарности U = {fmt(quality.util_u, 2)}; "
            f"сопоставимая избыточность G = {fmt(quality.util_g, 2)} г/100 г белка."
        )

    level, headline = _level(complete, confirmed, ref_name)
    return {
        "level": level,
        "headline": headline,
        "points": points,
        "reference": {
            "name": ref_name,
            "year": reference.get("year"),
            "source": reference.get("source"),
        },
        "criterion": CRITERION,
        "deficits": deficits,
        "limitations": limitations,
        "explanation": explain_indicators(quality),
        "experimental_note": EXPERIMENTAL_NOTE,
    }


def explain_indicators(quality: Quality) -> list[dict]:
    """Словами: что означает каждый показатель; числа — из расчёта, оценок нет."""
    rows = [
        {
            "code": "КРАС",
            "title": "Коэффициент различия аминокислотного скора",
            "value": round(quality.kras, 1),
            "unit": "%",
            "text": (
                "Среднее превышение скоров остальных аминокислот над скором "
                "лимитирующей. Чем меньше, тем ближе состав к сбалансированному. "
                "Пороговых значений для оценки в программе нет."
            ),
        },
        {
            "code": "БЦ",
            "title": "Биологическая ценность",
            "value": round(quality.bc, 1),
            "unit": "%",
            "text": "БЦ = 100 − КРАС. Чем выше, тем лучше сбалансирован белок.",
        },
    ]
    if quality.util_u is not None:
        rows.append(
            {
                "code": "U",
                "title": "Коэффициент утилитарности",
                "value": round(quality.util_u, 2),
                "unit": None,
                "text": (
                    "Доля незаменимых аминокислот, которую организм может "
                    "использовать при данной лимитирующей аминокислоте."
                ),
            }
        )
    if quality.util_g is not None:
        rows.append(
            {
                "code": "G",
                "title": "Сопоставимая избыточность",
                "value": round(quality.util_g, 2),
                "unit": "г/100 г белка",
                "text": (
                    "Масса аминокислот, которые при лимитирующей аминокислоте "
                    "не используются для построения белка организма."
                ),
            }
        )
    return rows
