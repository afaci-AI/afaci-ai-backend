"""Add nullable reference source metadata without changing amino-acid values.

Revision ID: e5f6a7b8c9d0
Revises: d3e4f5a6b7c8
"""

import sqlalchemy as sa

from alembic import op

revision = "e5f6a7b8c9d0"
down_revision = "d3e4f5a6b7c8"
branch_labels = None
depends_on = None


REFERENCE_SOURCES = [
    {
        "name": "ФАО/ВОЗ 1973",
        "description": "Провизорная шкала аминокислотного скора ФАО/ВОЗ 1973 г., основанная на данных о потребностях человека. Значения приведены по вторичному источнику Young и Pellett (1991), таблица 1, колонка FAO-WHO (1973). Сумма восьми незаменимых аминокислот равна 36 г/100 г белка. Шкала используется по умолчанию для воспроизведения исходного контрольного расчёта.",
        "source_title": "Protein Evaluation, Amino Acid Scoring and the Food and Drug Administration's Proposed Food Labeling Regulations",
        "source_authors": "Vernon R. Young; Peter L. Pellett. The Journal of Nutrition 121(1):145–150. DOI: 10.1093/jn/121.1.145",
        "source_year": 1991,
        "source_location": "Таблица 1, с. 147 (стр. 4 PDF), колонка FAO-WHO (1973). Вторичный источник.",
        "source_url": "https://downloads.regulations.gov/FDA-1990-N-0007-0213/attachment_1.pdf",
    },
    {
        "name": "ФАО/ВОЗ 1985",
        "description": "Эталон ФАО/ВОЗ/УООН 1985 г., построенный на профиле потребностей детей дошкольного возраста (2–5 лет). Значения воспроизведены в отчёте FAO 1991 г., таблица 7, колонка Pre-School Child (2–5 years). Требования к ряду незаменимых кислот ниже, чем в шкале 1973 г., поэтому аминокислотные скоры по нему, как правило, выше.",
        "source_title": "Protein quality evaluation. Report of the Joint FAO/WHO Expert Consultation. FAO Food and Nutrition Paper 51",
        "source_authors": "Food and Agriculture Organization of the United Nations; World Health Organization",
        "source_year": 1991,
        "source_location": "Таблица 7, с. 23 (стр. 29 PDF), Pre-School Child (2–5 years).",
        "source_url": "https://www.fao.org/4/t0501e/t0501e00.pdf",
    },
    {
        "name": "ФАО/ВОЗ 1991",
        "description": "Эталон ФАО/ВОЗ 1991 г. для оценки качества белка методом PDCAAS. Консультация рекомендовала профиль потребностей детей 2–5 лет для всех возрастов, кроме младенцев. Значения идентичны шкале ФАО/ВОЗ/УООН 1985 г. для детей 2–5 лет (таблица 7; разделы 6.2–6.3 отчёта).",
        "source_title": "Protein quality evaluation. Report of the Joint FAO/WHO Expert Consultation. FAO Food and Nutrition Paper 51",
        "source_authors": "Food and Agriculture Organization of the United Nations; World Health Organization",
        "source_year": 1991,
        "source_location": "Таблица 7, с. 23 (стр. 29 PDF); разделы 6.2–6.3, с. 23–25.",
        "source_url": "https://www.fao.org/4/t0501e/t0501e00.pdf",
    },
]


def upgrade() -> None:
    # seed_calculator.sql can create these columns before Alembic is applied.
    existing_columns = {
        column["name"]
        for column in sa.inspect(op.get_bind()).get_columns("reference_proteins")
    }
    for name, column_type in (
        ("source_title", sa.Text()),
        ("source_authors", sa.Text()),
        ("source_year", sa.Integer()),
        ("source_location", sa.Text()),
        ("source_url", sa.Text()),
        ("source_pdf_filename", sa.String()),
    ):
        if name not in existing_columns:
            op.add_column(
                "reference_proteins", sa.Column(name, column_type, nullable=True)
            )

    references = sa.table(
        "reference_proteins",
        sa.column("name", sa.String()),
        sa.column("description", sa.Text()),
        sa.column("source_title", sa.Text()),
        sa.column("source_authors", sa.Text()),
        sa.column("source_year", sa.Integer()),
        sa.column("source_location", sa.Text()),
        sa.column("source_url", sa.Text()),
        sa.column("source_pdf_filename", sa.String()),
    )
    for source in REFERENCE_SOURCES:
        values = {key: value for key, value in source.items() if key != "name"}
        # No PDF copy is licensed for this deployment; retain external links.
        values["source_pdf_filename"] = None
        op.execute(
            references.update()
            .where(references.c.name == source["name"])
            .values(**values)
        )


def downgrade() -> None:
    for name in (
        "source_pdf_filename",
        "source_url",
        "source_location",
        "source_year",
        "source_authors",
        "source_title",
    ):
        op.drop_column("reference_proteins", name)
