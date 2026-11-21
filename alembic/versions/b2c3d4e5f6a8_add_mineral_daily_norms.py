"""Add averaged daily norms for minerals (МР 2.3.1.0253-21, табл. 12, 13, 17, 18).

Нормы минералов для взрослых в документе заданы одной колонкой «старше 18 лет»
отдельно для мужчин (табл. 12, адекватные уровни — табл. 13) и женщин (табл. 17
и 18). Где значения различаются (Fe, Se), принято среднее, округлённое до целого,
как для энергии и БЖУ. Кальций — для взрослых до 64 лет (1000 мг; старше 65 —
1200 мг). Co и V — адекватные уровни потребления, а не физиологические нормы:
`kind = 'adequate'`. Единица нормы — единица документа (мг или мкг); значения
продуктов хранятся в мг/100 г и переводятся на backend.

Revision ID: b2c3d4e5f6a8
Revises: a1b2c3d4e5f7
"""

import uuid

import sqlalchemy as sa

from alembic import op

revision = "b2c3d4e5f6a8"
down_revision = "a1b2c3d4e5f7"
branch_labels = None
depends_on = None

MR_SOURCE_ID = uuid.UUID("5f0b0c1e-2a3b-4c5d-8e9f-0a1b2c3d4e5f")

_SAME = "МР 2.3.1.0253-21, табл. 12 и 17: {value} в сутки для мужчин и женщин старше 18 лет."
_ADEQUATE = (
    "МР 2.3.1.0253-21, табл. 13 и 18: адекватный уровень потребления {value} в сутки "
    "для мужчин и женщин старше 18 лет; физиологическая норма не установлена."
)


def _norm(key, unit, value, basis, order, kind="norm"):
    return {
        "key": key,
        "name": key,
        "unit": unit,
        "value": value,
        "basis": basis,
        "sort_order": order,
        "kind": kind,
    }


NORMS = [
    _norm(
        "Ca",
        "мг",
        1000.0,
        "МР 2.3.1.0253-21, табл. 12 и 17: 1000 мг в сутки для мужчин и женщин "
        "старше 18 лет; для лиц старше 65 лет — 1200 мг. Принята норма взрослых 18–64 лет.",
        20,
    ),
    _norm("P", "мг", 700.0, _SAME.format(value="700 мг"), 21),
    _norm("Mg", "мг", 420.0, _SAME.format(value="420 мг"), 22),
    _norm(
        "K",
        "мг",
        3500.0,
        "МР 2.3.1.0253-21, табл. 12 и 17: уточнённая физиологическая потребность "
        "3500 мг в сутки для мужчин и женщин старше 18 лет.",
        23,
    ),
    _norm(
        "Na",
        "мг",
        1300.0,
        "МР 2.3.1.0253-21, табл. 12 и 17: физиологическая потребность 1300 мг в сутки "
        "для мужчин и женщин старше 18 лет; поступление натрия с пищей не должно "
        "превышать 2 г в сутки.",
        24,
    ),
    _norm(
        "Fe",
        "мг",
        14.0,
        "МР 2.3.1.0253-21, табл. 12 и 17: 10 мг в сутки для мужчин и 18 мг для женщин "
        "старше 18 лет; принято среднее — 14 мг.",
        25,
    ),
    _norm("Zn", "мг", 12.0, _SAME.format(value="12 мг"), 26),
    _norm("Cu", "мг", 1.0, _SAME.format(value="1,0 мг"), 27),
    _norm("Mn", "мг", 2.0, _SAME.format(value="2,0 мг"), 28),
    _norm(
        "Se",
        "мкг",
        63.0,
        "МР 2.3.1.0253-21, табл. 12 и 17: 70 мкг в сутки для мужчин и 55 мкг для "
        "женщин старше 18 лет; среднее 62,5 мкг, округлено до 63 мкг.",
        29,
    ),
    _norm("I", "мкг", 150.0, _SAME.format(value="150 мкг"), 30),
    _norm(
        "Cr",
        "мкг",
        40.0,
        "МР 2.3.1.0253-21, табл. 12 и 17: уточнённая физиологическая потребность "
        "40 мкг в сутки для мужчин и женщин старше 18 лет.",
        31,
    ),
    _norm("Co", "мкг", 10.0, _ADEQUATE.format(value="10 мкг"), 32, "adequate"),
    _norm("V", "мкг", 15.0, _ADEQUATE.format(value="15 мкг"), 33, "adequate"),
]

LOCATION_BEFORE = (
    "Утверждены Главным государственным санитарным врачом РФ 22.07.2021, взамен "
    "МР 2.3.1.2432-08. Таблицы 9 и 14 (нормы для взрослых), приложение 3 "
    "(энергетическая ценность пищевых веществ)."
)
LOCATION_AFTER = (
    "Утверждены Главным государственным санитарным врачом РФ 22.07.2021, взамен "
    "МР 2.3.1.2432-08. Таблицы 9 и 14 (нормы для взрослых), 12, 13, 17 и 18 "
    "(минеральные вещества), приложение 3 (энергетическая ценность пищевых веществ)."
)
USED_FOR_BEFORE = (
    "Суточные нормы энергии, белков, жиров, углеводов и пищевых волокон; "
    "коэффициенты энергетической ценности."
)
USED_FOR_AFTER = (
    "Суточные нормы энергии, белков, жиров, углеводов, пищевых волокон и минеральных "
    "веществ; коэффициенты энергетической ценности."
)


def _set_source(location: str, used_for: str) -> None:
    op.execute(
        sa.text(
            "UPDATE sources SET location = :location, used_for = :used_for WHERE id = :id"
        ).bindparams(location=location, used_for=used_for, id=MR_SOURCE_ID)
    )


def upgrade() -> None:
    op.add_column(
        "daily_norms",
        sa.Column("kind", sa.String(), nullable=False, server_default="norm"),
    )
    op.create_check_constraint(
        "ck_daily_norm_kind", "daily_norms", "kind IN ('norm', 'adequate')"
    )
    norms = sa.table(
        "daily_norms",
        sa.column("id", sa.UUID()),
        sa.column("key", sa.String()),
        sa.column("name", sa.String()),
        sa.column("unit", sa.String()),
        sa.column("value", sa.Double()),
        sa.column("source_id", sa.UUID()),
        sa.column("basis", sa.Text()),
        sa.column("sort_order", sa.Integer()),
        sa.column("kind", sa.String()),
    )
    op.bulk_insert(
        norms,
        [
            {
                **norm,
                "id": uuid.uuid5(MR_SOURCE_ID, norm["key"]),
                "source_id": MR_SOURCE_ID,
            }
            for norm in NORMS
        ],
    )
    _set_source(LOCATION_AFTER, USED_FOR_AFTER)


def downgrade() -> None:
    _set_source(LOCATION_BEFORE, USED_FOR_BEFORE)
    op.execute(
        sa.text("DELETE FROM daily_norms WHERE key IN :keys").bindparams(
            sa.bindparam("keys", [norm["key"] for norm in NORMS], expanding=True)
        )
    )
    op.drop_constraint("ck_daily_norm_kind", "daily_norms", type_="check")
    op.drop_column("daily_norms", "kind")
