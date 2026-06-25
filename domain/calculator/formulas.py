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
                              αⱼ = Cmin/Cⱼ,  V = Σ(αⱼ·Aⱼ)/ΣAⱼ,
                              G = Σ(Aⱼ·(1−αⱼ)) / (Cmin/100)
"""
from __future__ import annotations

# Порядок и состав групп незаменимых аминокислот (НАК).
# Группа -> список названий аминокислот в БД, которые её формируют.
NAK_GROUPS: list[tuple[str, list[str]]] = [
    ("ИЗО",     ["Изолейцин"]),
    ("ЛЕЙ",     ["Лейцин"]),
    ("ВАЛ",     ["Валин"]),
    ("МЕТ+ЦИС", ["Метионин", "Цистеин"]),
    ("Ф+Т",     ["Фенилаланин", "Тирозин"]),
    ("ТРИ",     ["Триптофан"]),
    ("ТРЕ",     ["Треонин"]),
    ("ЛИЗ",     ["Лизин"]),
]

SUM_TOLERANCE = 0.01  # допуск на сумму Xᵢ (борьба с ошибкой float)
REQUIRED_SUM = 100.0


def _round(value: float | None, digits: int) -> float | None:
    return None if value is None else round(value, digits)


def compute_report(items: list[dict], reference: dict) -> dict:
    """
    items: [{product_id, name, region, subcategory, amount_g,
             chem: {"Массовая доля белка": x, "Массовая доля жира": x,
                    "Углеводы": x, "Пищевые волокна": x},
             amino: {"Изолейцин": мг/100г, ...}}]
    reference: {id, name, year, description, values: {"ИЗО": 4.0, ...}}
    """
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
    protein_base = sum(it["chem"].get("Массовая доля белка", 0.0) * it["amount_g"]
                       for it in contributors)

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
                m_ij = group_mg / (p * 10.0)          # г/100 г белка
                numerator += p * it["amount_g"] * m_ij
            m_j = numerator / protein_base
            ref_val = reference["values"].get(group)
            score = (m_j / ref_val * 100.0) if ref_val else None
            amino_rows.append({"name": group, "m_j": m_j, "reference": ref_val, "score": score})

    # ---- Cmin, лимитирующие НАК ----
    scored = [r for r in amino_rows if r["score"] is not None]
    c_min_val = min((r["score"] for r in scored), default=None)
    c_min_name = next((r["name"] for r in scored if r["score"] == c_min_val), None)

    # ---- Этап 4. Качественные показатели ----
    kras = bc = util_V = util_G = None
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
        util_V = sum_alpha_A / sum_A if sum_A else None
        util_G = sum_excess / (c_min_val / 100.0) if c_min_val else None

    # Пометить лимитирующие и минимальную НАК
    for r in amino_rows:
        r["is_limiting"] = r["score"] is not None and r["score"] < 100
        r["is_min"] = r["name"] == c_min_name

    limiting = [r["name"] for r in amino_rows if r["is_limiting"]]

    # Предупреждение: белоксодержащие ингредиенты без данных по НАК
    no_amino_protein = [
        it["name"] for it in items
        if not it.get("amino") and it["chem"].get("Массовая доля белка", 0.0) > 0
    ]
    warnings: list[str] = []
    if no_amino_protein:
        warnings.append(
            "В аминокислотном расчёте не учтены ингредиенты без данных по НАК "
            "(вклад в макросостав сохранён): " + ", ".join(no_amino_protein) + "."
        )

    verdict = _build_verdict(
        c_min_name, c_min_val, kras, bc, util_V, util_G, len(limiting),
        protein, fat,
    )

    return {
        "recipe": [
            {
                "product_id": it["product_id"],
                "name": it["name"],
                "region": it.get("region"),
                "subcategory": it.get("subcategory"),
                "amount_g": _round(it["amount_g"], 2),
            }
            for it in items
        ],
        "sum_g": _round(total_g, 2),
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
            "protein": _round(protein, 2),
            "fat": _round(fat, 2),
            "carb": _round(carb, 2),
            "fiber": _round(fiber, 2),
            "protein_fat_ratio": _round(fat / protein, 2) if protein else None,
        },
        "energy_kcal": _round(energy, 1),
        "amino_acids": [
            {
                "name": r["name"],
                "m_j": _round(r["m_j"], 2),
                "reference": r["reference"],
                "score": _round(r["score"], 1),
                "utility": _round(r.get("utility"), 2),
                "is_limiting": r["is_limiting"],
                "is_min": r["is_min"],
            }
            for r in amino_rows
        ],
        "c_min": {"name": c_min_name, "score": _round(c_min_val, 1)} if c_min_name else None,
        "limiting": limiting,
        "limiting_count": len(limiting),
        "quality": {
            "kras": _round(kras, 1),
            "bc": _round(bc, 1),
            "V": _round(util_V, 2),
            "G": _round(util_G, 2),
        },
        "amino_contributors": [it["name"] for it in contributors],
        "warnings": warnings,
        "verdict": verdict,
    }


# Пороговые уровни итогового уровня качества
_LEVEL_ORDER = {"good": 0, "moderate": 1, "poor": 2}
_LEVEL_HEADLINE = {
    "good": "Белок высокого качества",
    "moderate": "Белок удовлетворительного качества",
    "poor": "Белок низкого качества",
}


def _build_verdict(c_min_name, c_min_val, kras, bc, util_V, util_G,
                   limiting_count, protein, fat) -> dict | None:
    """
    Текстовый вердикт по качеству белка — интерпретация уже посчитанных
    показателей (Cmin, КРАС/БЦ, V, G) словами. БЕЗ обращения к банку продуктов.
    Возвращает {level, headline, points[]}.
    """
    if c_min_val is None or kras is None:
        return None

    points: list[str] = []

    # 1. Полноценность — по минимальному скору (Cmin)
    if c_min_val >= 95:
        completeness = "good"
        points.append(
            f"Белок практически полноценный: минимальный аминокислотный скор "
            f"{c_min_val:.0f}% — все незаменимые аминокислоты близки к эталону или выше."
        )
    elif c_min_val >= 70:
        completeness = "moderate"
        points.append(
            f"Лимитирующая аминокислота — {c_min_name} (скор {c_min_val:.0f}%). "
            f"Именно она ограничивает биологическую ценность белка"
            + (f"; всего лимитирующих НАК: {limiting_count}." if limiting_count else ".")
        )
    else:
        completeness = "poor"
        points.append(
            f"Выраженный дефицит по аминокислоте {c_min_name} (скор {c_min_val:.0f}%): "
            f"белок неполноценный, биологическая ценность сильно ограничена."
        )

    # 2. Сбалансированность — по КРАС/БЦ
    if kras < 10:
        balance = "good"
        points.append(
            f"Аминокислотный состав хорошо сбалансирован: КРАС {kras:.1f}%, "
            f"биологическая ценность {bc:.1f}% — близко к идеальному белку."
        )
    elif kras < 25:
        balance = "moderate"
        points.append(
            f"Умеренный дисбаланс: КРАС {kras:.1f}%, БЦ {bc:.1f}%. Часть незаменимых "
            f"аминокислот в избытке относительно лимитирующей и используется не полностью."
        )
    else:
        balance = "poor"
        points.append(
            f"Сильный дисбаланс: КРАС {kras:.1f}%, БЦ {bc:.1f}% — много «избыточных» "
            f"аминокислот, не подкреплённых лимитирующей."
        )

    # 3. Утилизация и избыточность (V, G)
    if util_V is not None and util_G is not None:
        points.append(
            f"Коэффициент утилитарности V = {util_V:.2f}: незаменимые аминокислоты "
            f"используются примерно на {util_V * 100:.0f}%. Сопоставимая избыточность "
            f"G = {util_G:.1f} г/100 г белка не идёт на пластические нужды."
        )

    # 4. Краткая заметка по макросоставу (тоже только текст, без банка)
    if protein and fat:
        ratio = fat / protein
        if protein < 12:
            points.append(
                f"Доля белка невысокая ({protein:.1f}%) при соотношении белок:жир "
                f"1:{ratio:.2f} — для повышения пищевой ценности есть смысл увеличить "
                f"белковую часть и снизить жировую."
            )

    level = max([completeness, balance], key=lambda x: _LEVEL_ORDER[x])
    return {"level": level, "headline": _LEVEL_HEADLINE[level], "points": points}
