"""
Расчёт пищевой и биологической ценности рецептуры (методика Липатова).

Чистая вычислительная логика — без обращения к БД, поэтому легко тестируется.
Маршрут `api/v1/calculator.py` подготавливает данные из БД и вызывает
`compute_report`.

Все формулы соответствуют документу «Решение по формулам (контроль)»:

  Этап 1. Макросостав:        S = Σ(Sᵢ·Xᵢ) / 100
  Этап 2. НАК и скор:         Mⱼ = Σ(Sᵢ·Xᵢ·Mᵢⱼ) / Σ(Sᵢ·Xᵢ),  C = Mⱼ/эталон·100
  Этап 3. Энергоценность:     ЭЦ = 4·Б + 9·Ж + 4·У
  Этап 4. Качество:           КРАС = Σ(Cⱼ−Cmin)/n,  БЦ = 100−КРАС,
                              αⱼ = Cmin/Cⱼ,  U = Σ(αⱼ·Aⱼ)/ΣAⱼ,
                              G = Σ(Aⱼ·(1−αⱼ)) / (Cmin/100)
"""

from __future__ import annotations

# Порядок и состав групп незаменимых аминокислот (НАК).
# Группа -> список названий аминокислот в БД, которые её формируют.
NAK_GROUPS: list[tuple[str, list[str]]] = [
    ("ИЗО", ["Изолейцин"]),
    ("ЛЕЙ", ["Лейцин"]),
    ("ВАЛ", ["Валин"]),
    ("МЕТ+ЦИС", ["Метионин", "Цистеин"]),
    ("Ф+Т", ["Фенилаланин", "Тирозин"]),
    ("ТРИ", ["Триптофан"]),
    ("ТРЕ", ["Треонин"]),
    ("ЛИЗ", ["Лизин"]),
]

SUM_TOLERANCE = 0.01  # допуск на сумму Xᵢ (борьба с ошибкой float)
REQUIRED_SUM = 100.0


def _round(value: float | None, digits: int) -> float | None:
    return None if value is None else round(value, digits)


def compute_report(items: list[dict], reference: dict, *, rounded: bool = True) -> dict:
    """
    items: [{product_id, name, region, subcategory, amount_g,
             chem: {"Массовая доля белка": x, "Массовая доля жира": x,
                    "Углеводы": x, "Пищевые волокна": x},
             amino: {"Изолейцин": мг/100г, ...}}]
    reference: {id, name, year, description, values: {"ИЗО": 4.0, ...}}
    """

    def display(value: float | None, digits: int) -> float | None:
        return _round(value, digits) if rounded else value

    total_g = sum(it["amount_g"] for it in items)

    # ---- Этап 1. Макросостав, % ----
    def macro(name: str) -> float:
        return sum(it["chem"].get(name, 0.0) * it["amount_g"] for it in items) / 100.0

    protein = macro("Массовая доля белка")
    fat = macro("Массовая доля жира")
    carb = macro("Углеводы")
    fiber = macro("Пищевые волокна")

    # ---- Этап 3. Энергетическая ценность ----
    energy = 4 * protein + 9 * fat + 4 * carb

    # ---- Этап 2. НАК суммарного белка и аминокислотный скор ----
    # Вклад в белок учитывают только ингредиенты, у которых есть данные по НАК.
    contributors = [it for it in items if it.get("amino")]
    protein_base = sum(
        it["chem"].get("Массовая доля белка", 0.0) * it["amount_g"]
        for it in contributors
    )

    amino_rows: list[dict] = []
    if contributors and protein_base > 0:
        for group, members in NAK_GROUPS:
            # Mⱼ = Σ(белокᵢ·Xᵢ·Mᵢⱼ) / Σ(белокᵢ·Xᵢ),  Mᵢⱼ = мг_группы / (белок%·10)
            numerator = 0.0
            for it in contributors:
                p = it["chem"].get("Массовая доля белка", 0.0)
                if p <= 0:
                    continue
                group_mg = sum(it["amino"].get(m, 0.0) for m in members)
                m_ij = group_mg / (p * 10.0)  # г/100 г белка
                numerator += p * it["amount_g"] * m_ij
            m_j = numerator / protein_base
            ref_val = reference["values"].get(group)
            score = (m_j / ref_val * 100.0) if ref_val else None
            amino_rows.append(
                {"name": group, "m_j": m_j, "reference": ref_val, "score": score}
            )

    # ---- Cmin, лимитирующие НАК ----
    scored = [r for r in amino_rows if r["score"] is not None]
    c_min_val = min((r["score"] for r in scored), default=None)
    c_min_name = next((r["name"] for r in scored if r["score"] == c_min_val), None)

    # ---- Этап 4. Качественные показатели ----
    kras = bc = util_U = util_G = None
    if scored and c_min_val is not None:
        n = len(scored)
        kras = sum(r["score"] - c_min_val for r in scored) / n
        bc = 100.0 - kras

        sum_alpha_A = 0.0
        sum_A = 0.0
        sum_excess = 0.0
        for r in scored:
            alpha = c_min_val / r["score"] if r["score"] else 0.0
            r["utility"] = alpha
            A = r["m_j"]
            sum_alpha_A += alpha * A
            sum_A += A
            sum_excess += A * (1 - alpha)
        util_U = sum_alpha_A / sum_A if sum_A else None
        util_G = sum_excess / (c_min_val / 100.0) if c_min_val else None

    # Пометить лимитирующие и минимальную НАК
    for r in amino_rows:
        r["is_limiting"] = r["score"] is not None and r["score"] < 100
        r["is_min"] = r["name"] == c_min_name

    limiting = [r["name"] for r in amino_rows if r["is_limiting"]]

    # Предупреждение: белоксодержащие ингредиенты без данных по НАК
    no_amino_protein = [
        it["name"]
        for it in items
        if not it.get("amino") and it["chem"].get("Массовая доля белка", 0.0) > 0
    ]
    warnings: list[str] = []
    if no_amino_protein:
        warnings.append(
            "В аминокислотном расчёте не учтены ингредиенты без данных по НАК "
            "(вклад в макросостав сохранён): " + ", ".join(no_amino_protein) + "."
        )

    macro_names = {
        "Массовая доля белка": "белок",
        "Массовая доля жира": "жир",
        "Углеводы": "углеводы",
        "Пищевые волокна": "пищевые волокна",
    }
    missing_chem = []
    for it in items:
        if it["amount_g"] <= 0:
            continue
        missing = [label for key, label in macro_names.items() if key not in it["chem"]]
        if missing:
            missing_chem.append(f"{it['name']} ({', '.join(missing)})")
    if missing_chem:
        warnings.append(
            "Отсутствуют данные химического состава: "
            + "; ".join(missing_chem)
            + ". Макросостав и энергетическая ценность рассчитаны только по известным "
            "данным; отсутствие значения не означает нулевое содержание."
        )

    verdict = _build_verdict(amino_rows, reference, kras, bc, util_U, util_G)

    return {
        "recipe": [
            {
                "product_id": it["product_id"],
                "name": it["name"],
                "region": it.get("region"),
                "subcategory": it.get("subcategory"),
                "amount_g": display(it["amount_g"], 2),
            }
            for it in items
        ],
        "sum_g": display(total_g, 2),
        "reference": {
            "id": reference["id"],
            "name": reference["name"],
            "year": reference.get("year"),
            "description": reference.get("description"),
            "values": [
                {"amino_acid": g, "value": reference["values"].get(g)}
                for g, _ in NAK_GROUPS
            ],
        },
        "macro": {
            "protein": display(protein, 2),
            "fat": display(fat, 2),
            "carb": display(carb, 2),
            "fiber": display(fiber, 2),
            "protein_fat_ratio": display(fat / protein, 2) if protein else None,
        },
        "energy_kcal": display(energy, 1),
        "amino_acids": [
            {
                "name": r["name"],
                "m_j": display(r["m_j"], 2),
                "reference": r["reference"],
                "score": display(r["score"], 1),
                "utility": display(r.get("utility"), 2),
                "is_limiting": r["is_limiting"],
                "is_min": r["is_min"],
            }
            for r in amino_rows
        ],
        "c_min": {"name": c_min_name, "score": display(c_min_val, 1)}
        if c_min_name
        else None,
        "limiting": limiting,
        "limiting_count": len(limiting),
        "quality": {
            "kras": display(kras, 1),
            "bc": display(bc, 1),
            "U": display(util_U, 2),
            # Устаревший псевдоним U для выпущенных клиентов; будет удалён.
            "V": display(util_U, 2),
            "G": display(util_G, 2),
        },
        # Raw values support numerical comparison without treating display rounding
        # as evidence that the composition improved.
        "quality_precise": {
            "kras": kras,
            "bc": bc,
            "U": util_U,
            "V": util_U,  # устаревший псевдоним U
            "G": util_G,
        },
        "amino_contributors": [it["name"] for it in contributors],
        "warnings": warnings,
        "verdict": verdict,
    }


EXPERIMENTAL_NOTE = (
    "Экспериментальная функция. Заключение строится только по аминокислотному "
    "составу белка в сравнении с выбранным эталоном ФАО/ВОЗ; усвояемость и другие "
    "факторы не учитываются."
)


def _fmt(value: float, digits: int = 1) -> str:
    """Число с десятичной запятой для текста заключения."""
    return f"{value:.{digits}f}".replace(".", ",")


def _build_verdict(
    amino_rows: list[dict],
    reference: dict,
    kras: float | None,
    bc: float | None,
    util_U: float | None,
    util_G: float | None,
) -> dict | None:
    """
    Заключение о белке строго по выбранному эталону ФАО/ВОЗ — без условных порогов.

    Критерий один: белок полноценен по эталону, если содержание каждой из
    8 групп НАК не ниже эталона (скор ≥ 100 %). Иначе перечисляются НАК ниже
    эталона с их скором и недостачей в г/100 г белка. КРАС, БЦ, U и G выводятся
    числами, без оценочных слов. Усвояемость белка не учитывается.

    Возвращает {level, headline, points[], reference, deficits[], experimental_note}
    или None, если расчёт скоров невозможен. Без обращения к банку продуктов.
    """
    scored = [r for r in amino_rows if r["score"] is not None]
    if not scored or kras is None or bc is None:
        return None

    ref_name = reference["name"]
    deficits = sorted(
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
    complete = not deficits

    points: list[str] = [
        (
            f"Оценка выполнена по эталону «{ref_name}»: содержание каждой группы "
            f"незаменимых аминокислот в белке рецептуры сравнивается со значением "
            f"эталона (г на 100 г белка). Усвояемость белка не учитывается."
        )
    ]
    if complete:
        points.append(
            f"Все {len(scored)} групп незаменимых аминокислот не ниже эталона "
            f"(аминокислотный скор ≥ 100 %): по эталону белок полноценный."
        )
    else:
        lowest = deficits[0]
        points.append(
            f"Ниже эталона {len(deficits)} из {len(scored)} групп незаменимых "
            f"аминокислот. Лимитирующая — {lowest['name']}: скор "
            f"{_fmt(lowest['score'])} %."
        )
        points.extend(
            f"{d['name']}: скор {_fmt(d['score'])} % — {_fmt(d['m_j'], 2)} г против "
            f"{_fmt(d['reference'], 2)} г на 100 г белка, недостаёт "
            f"{_fmt(d['deficit'], 2)} г."
            for d in deficits
        )
    points.append(f"Расчётные показатели: КРАС = {_fmt(kras)} %, БЦ = {_fmt(bc)} %.")
    if util_U is not None and util_G is not None:
        points.append(
            f"Справочно: коэффициент утилитарности U = {_fmt(util_U, 2)}; "
            f"сопоставимая избыточность G = {_fmt(util_G, 2)} г/100 г белка."
        )

    return {
        "level": "complete" if complete else "incomplete",
        "headline": (
            f"Белок полноценный по эталону {ref_name}"
            if complete
            else f"Белок неполноценный по эталону {ref_name}"
        ),
        "points": points,
        "reference": {"name": ref_name, "year": reference.get("year")},
        "deficits": deficits,
        "experimental_note": EXPERIMENTAL_NOTE,
    }
