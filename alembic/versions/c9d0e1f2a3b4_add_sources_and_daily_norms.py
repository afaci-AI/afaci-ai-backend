"""Add sources registry and averaged daily norms (МР 2.3.1.0253-21).

Таблицы:
  * sources     — документы, статьи и ссылки, на которые опирается программа;
  * daily_norms — усреднённые суточные нормы (энергия, белки, жиры, углеводы,
                  пищевые волокна) со ссылкой на источник.

Нормы внесены из текста МР 2.3.1.0253-21 (табл. 9 и 14): одна усреднённая величина
для взрослых 18–64 лет — среднее арифметическое по 24 группам (мужчины и женщины,
возрасты 18–29, 30–44, 45–64, четыре группы физической активности), округлённое
до целого. Значения групп и расчёт среднего проверяются тестом
`tests/test_daily_norms.py`. Источники эталонных белков остаются в
`reference_proteins` и показываются в общем реестре на уровне API.

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
"""

import uuid

import sqlalchemy as sa

from alembic import op

revision = "c9d0e1f2a3b4"
down_revision = "b8c9d0e1f2a3"
branch_labels = None
depends_on = None

MR_SOURCE_ID = uuid.UUID("5f0b0c1e-2a3b-4c5d-8e9f-0a1b2c3d4e5f")

MR_SOURCE = {
    "id": MR_SOURCE_ID,
    "kind": "document",
    "title": (
        "МР 2.3.1.0253-21. 2.3.1. Гигиена питания. Рациональное питание. Нормы "
        "физиологических потребностей в энергии и пищевых веществах для различных "
        "групп населения Российской Федерации. Методические рекомендации"
    ),
    "authors": (
        "Федеральная служба по надзору в сфере защиты прав потребителей и "
        "благополучия человека (Роспотребнадзор)"
    ),
    "year": 2021,
    "location": (
        "Утверждены Главным государственным санитарным врачом РФ 22.07.2021, взамен "
        "МР 2.3.1.2432-08. Таблицы 9 и 14 (нормы для взрослых), приложение 3 "
        "(энергетическая ценность пищевых веществ)."
    ),
    "url": "https://legalacts.ru/doc/mr-2310253-21-231-gigiena-gigiena-pitanija-ratsionalnoe-pitanie-normy/",
    "pdf_filename": None,
    "used_for": (
        "Суточные нормы энергии, белков, жиров, углеводов и пищевых волокон; "
        "коэффициенты энергетической ценности."
    ),
    "sort_order": 10,
}

_AVERAGING = (
    "Среднее арифметическое норм для 24 групп взрослых 18–64 лет (мужчины и женщины × "
    "возрасты 18–29, 30–44, 45–64 × четыре группы физической активности), "
    "МР 2.3.1.0253-21, табл. 9 и 14: {exact}, округлено до {value}."
)

NORMS = [
    {
        "key": "energy",
        "name": "Энергетическая ценность",
        "unit": "ккал",
        "value": 2602.0,
        "basis": _AVERAGING.format(exact="2602,08 ккал", value="2602 ккал"),
        "sort_order": 1,
    },
    {
        "key": "protein",
        "name": "Белки",
        "unit": "г",
        "value": 83.0,
        "basis": _AVERAGING.format(exact="83,04 г", value="83 г"),
        "sort_order": 2,
    },
    {
        "key": "fat",
        "name": "Жиры",
        "unit": "г",
        "value": 87.0,
        "basis": _AVERAGING.format(exact="86,79 г", value="87 г"),
        "sort_order": 3,
    },
    {
        "key": "carbs",
        "name": "Углеводы",
        "unit": "г",
        "value": 372.0,
        "basis": _AVERAGING.format(exact="372,46 г", value="372 г"),
        "sort_order": 4,
    },
    {
        "key": "fiber",
        "name": "Пищевые волокна",
        "unit": "г",
        "value": 25.0,
        "basis": (
            "МР 2.3.1.0253-21, п. 4.2.1.3: для взрослых 20–25 г в сутки (одно значение "
            "для всех групп; также 10 г на 1000 ккал). Принята верхняя граница "
            "диапазона."
        ),
        "sort_order": 5,
    },
]


def upgrade() -> None:
    op.create_table(
        "sources",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("authors", sa.Text(), nullable=True),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column("location", sa.Text(), nullable=True),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("pdf_filename", sa.String(), nullable=True),
        sa.Column("used_for", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.CheckConstraint(
            "kind IN ('article', 'document', 'book', 'link', 'file')",
            name="ck_sources_kind",
        ),
    )
    op.create_table(
        "daily_norms",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("key", sa.String(), nullable=False, unique=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("unit", sa.String(), nullable=False),
        sa.Column("value", sa.Double(), nullable=False),
        sa.Column("source_id", sa.UUID(), sa.ForeignKey("sources.id"), nullable=False),
        sa.Column("basis", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
    )
    sources = sa.table(
        "sources",
        sa.column("id", sa.UUID()),
        sa.column("kind", sa.String()),
        sa.column("title", sa.Text()),
        sa.column("authors", sa.Text()),
        sa.column("year", sa.Integer()),
        sa.column("location", sa.Text()),
        sa.column("url", sa.Text()),
        sa.column("pdf_filename", sa.String()),
        sa.column("used_for", sa.Text()),
        sa.column("sort_order", sa.Integer()),
    )
    op.bulk_insert(sources, [MR_SOURCE])
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


def downgrade() -> None:
    op.drop_table("daily_norms")
    op.drop_table("sources")
