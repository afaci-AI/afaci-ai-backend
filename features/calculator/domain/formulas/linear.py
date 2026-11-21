"""Линейные формы показателей белка для оптимизаторов.

Показатели методики (КРАС, БЦ, U, G) нелинейны по массам Xᵢ, но построены на
двух линейных формах — суммарном НАК группы и белковой базе:

    Nⱼ(x) = Σᵢ aᵢⱼ·xᵢ,   aᵢⱼ = (мг группы j в 100 г ингредиента) / 10
    B(x)  = Σᵢ pᵢ·xᵢ,    pᵢ — массовая доля белка, %

Через них Mⱼ = Nⱼ/B и скор Cⱼ = 100·Nⱼ / (rⱼ·B), поэтому после умножения на
B > 0 ограничения «КРАС ≤ K» и «t ≥ t₀» становятся линейными. Правила отбора
те же, что в `amino.py`: в формах участвуют только ингредиенты с профилем НАК,
а вклад в Nⱼ дают лишь те из них, у которых белок > 0.

Связь показателей с t = Cmin / ΣMⱼ (вывод — в `docs/architecture-decisions.md`):

    U = R·t/100,   G = 100/t − R,   R = Σⱼ rⱼ

поэтому U ≥ U₀ и G ≤ G₀ сводятся к одному ограничению t ≥ t₀.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .constants import NAK_GROUPS, PROTEIN


@dataclass(frozen=True)
class LinearForms:
    """Коэффициенты линейных форм для набора кандидатов и эталона.

    `amino` — матрица aᵢⱼ (ингредиенты × группы НАК), `protein_base` — pᵢ по
    ингредиентам с профилем НАК (база B методики), `protein_macro` — pᵢ по всем
    ингредиентам (массовая доля белка рецептуры), `reference` — rⱼ по тем же
    группам, что и столбцы `amino`.
    """

    amino: np.ndarray
    protein_base: np.ndarray
    protein_macro: np.ndarray
    reference: np.ndarray
    groups: tuple[str, ...]

    @property
    def group_count(self) -> int:
        return len(self.groups)

    @property
    def reference_sum(self) -> float:
        """R = Σⱼ rⱼ — входит в связь U и G с t."""
        return float(self.reference.sum())

    def amino_totals(self, amounts: np.ndarray) -> np.ndarray:
        """Nⱼ(x) по группам НАК."""
        return self.amino.T @ np.asarray(amounts, dtype=float)

    def base(self, amounts: np.ndarray) -> float:
        """B(x) — белковая база скоров."""
        return float(self.protein_base @ np.asarray(amounts, dtype=float))

    def scores(self, amounts: np.ndarray) -> np.ndarray | None:
        """Скоры Cⱼ = 100·Nⱼ/(rⱼ·B); `None`, если белковая база нулевая."""
        base = self.base(amounts)
        if base <= 0:
            return None
        return 100.0 * self.amino_totals(amounts) / (self.reference * base)

    def scaled_scores(self, amounts: np.ndarray) -> np.ndarray:
        """Cⱼ·B = 100·Nⱼ/rⱼ — линейная форма, на ней строятся ограничения."""
        return 100.0 * self.amino_totals(amounts) / self.reference

    def score_rows(self) -> np.ndarray:
        """Коэффициенты Cⱼ·B по ингредиентам: строка j — 100·aᵢⱼ/rⱼ."""
        return 100.0 * self.amino.T / self.reference[:, None]


def _group_amount(item: dict, members: list[str]) -> float:
    """aᵢⱼ: мг группы НАК в 100 г продукта, делённые на 10.

    Повторяет `amino.py`: Mᵢⱼ = мг / (белок%·10), а в числитель Mⱼ входит
    произведение pᵢ·Mᵢⱼ, то есть мг/10 — белок сокращается.
    """
    protein = item["chem"].get(PROTEIN, 0.0)
    if protein <= 0:
        return 0.0
    return sum(item["amino"].get(member, 0.0) for member in members) / 10.0


def build_forms(items: list[dict], reference: dict) -> LinearForms:
    """Коэффициенты линейных форм по кандидатам в формате `compute_report`.

    Учитываются только группы НАК с положительным значением эталона — те же,
    по которым `quality.py` считает КРАС, БЦ, U и G.
    """
    groups = [
        (group, members)
        for group, members in NAK_GROUPS
        if (reference.get("values", {}).get(group) or 0.0) > 0
    ]
    contributors = [bool(item.get("amino")) for item in items]
    amino = np.array(
        [
            [
                _group_amount(item, members) if has_amino else 0.0
                for _, members in groups
            ]
            for item, has_amino in zip(items, contributors, strict=True)
        ],
        dtype=float,
    ).reshape(len(items), len(groups))
    protein_macro = np.array(
        [float(item["chem"].get(PROTEIN, 0.0)) for item in items], dtype=float
    )
    protein_base = np.where(contributors, protein_macro, 0.0)
    values = np.array(
        [float(reference["values"][group]) for group, _ in groups], dtype=float
    )
    return LinearForms(
        amino=amino,
        protein_base=protein_base,
        protein_macro=protein_macro,
        reference=values,
        groups=tuple(group for group, _ in groups),
    )


def indicators(forms: LinearForms, amounts: np.ndarray) -> dict | None:
    """КРАС, БЦ, U и G по линейным формам; `None`, если скоры не определены.

    Нужно для проверок: те же числа даёт `compute_report`.
    """
    scores = forms.scores(amounts)
    if scores is None or not np.isfinite(scores).all():
        return None
    c_min = float(scores.min())
    kras = float(scores.mean() - c_min)
    totals = forms.amino_totals(amounts)
    base = forms.base(amounts)
    m_sum = float(totals.sum()) / base
    if m_sum <= 0:
        return None
    t = c_min / m_sum
    reference_sum = forms.reference_sum
    return {
        "kras": kras,
        "bc": 100.0 - kras,
        "U": reference_sum * t / 100.0,
        "G": 100.0 / t - reference_sum if t > 0 else None,
    }
