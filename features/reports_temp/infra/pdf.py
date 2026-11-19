"""Рендер ReportDocument в PDF (ReportLab, шрифт DejaVu Sans с кириллицей)."""

from __future__ import annotations

import io
from functools import lru_cache
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from ..app.models import ReportDocument, ReportTable

FONT_DIR = Path(__file__).parent / "fonts"
REGULAR = "DejaVuSans"
BOLD = "DejaVuSans-Bold"
MARK = "Временный отчёт"
MARGIN = 15 * mm


@lru_cache(maxsize=1)
def _register_fonts() -> None:
    pdfmetrics.registerFont(TTFont(REGULAR, str(FONT_DIR / "DejaVuSans.ttf")))
    pdfmetrics.registerFont(TTFont(BOLD, str(FONT_DIR / "DejaVuSans-Bold.ttf")))
    pdfmetrics.registerFontFamily(REGULAR, normal=REGULAR, bold=BOLD)


def _style(name: str, **kw) -> ParagraphStyle:
    return ParagraphStyle(name, fontName=kw.pop("fontName", REGULAR), **kw)


class _NumberedCanvas(canvas.Canvas):
    """Две проходки: «Стр. X из Y» требует знать общее число страниц."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved: list[dict] = []

    def showPage(self):
        self._saved.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._saved)
        for state in self._saved:
            self.__dict__.update(state)
            self._footer(total)
            super().showPage()
        super().save()

    def _footer(self, total: int) -> None:
        width, _ = A4
        self.setFont(REGULAR, 8)
        self.setFillColor(colors.grey)
        self.drawString(MARGIN, 10 * mm, MARK)
        self.drawRightString(
            width - MARGIN, 10 * mm, f"Стр. {self._pageNumber} из {total}"
        )


def _para(text: str, style: ParagraphStyle) -> Paragraph:
    return Paragraph(escape(text), style)


def _table(spec: ReportTable, available: float) -> Table:
    head = _style("th", fontName=BOLD, fontSize=8, leading=10)
    cell = _style("td", fontSize=8, leading=10)
    right = _style("tdr", fontSize=8, leading=10, alignment=2)
    head_r = _style("thr", fontName=BOLD, fontSize=8, leading=10, alignment=2)

    def style_for(i: int, header: bool) -> ParagraphStyle:
        if spec.align[i] == "R":
            return head_r if header else right
        return head if header else cell

    data = [[_para(c, style_for(i, True)) for i, c in enumerate(spec.columns)]]
    for row in spec.rows:
        data.append([_para(v, style_for(i, False)) for i, v in enumerate(row)])
    total = sum(spec.widths)
    widths = [available * w / total for w in spec.widths]
    table = Table(data, colWidths=widths, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8eef2")),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#9aa5ad")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                (
                    "ROWBACKGROUNDS",
                    (0, 1),
                    (-1, -1),
                    [colors.white, colors.HexColor("#f6f8f9")],
                ),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    return table


def render_pdf(doc: ReportDocument) -> bytes:
    _register_fonts()
    buffer = io.BytesIO()
    width, _ = A4
    available = width - 2 * MARGIN
    template = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=MARGIN,
        bottomMargin=18 * mm,
        title=doc.title,
        author=doc.author,
    )
    title = _style("title", fontName=BOLD, fontSize=15, leading=19, spaceAfter=4)
    meta = _style("meta", fontSize=9, leading=12, textColor=colors.HexColor("#444444"))
    section = _style(
        "section", fontName=BOLD, fontSize=11, leading=14, spaceBefore=10, spaceAfter=4
    )
    note = _style("note", fontSize=8, leading=10, textColor=colors.HexColor("#555555"))
    empty = _style("empty", fontSize=11, leading=14, spaceBefore=12)

    story: list = [_para(doc.title, title)]
    story.append(_para(f"Сформирован: {doc.created_at:%d.%m.%Y %H:%M} UTC", meta))
    story.append(_para(f"Пользователь: {doc.author}", meta))
    for label, value in doc.criteria:
        story.append(_para(f"{label}: {value}", meta))
    story.append(Spacer(1, 6))
    if doc.empty_message:
        story.append(_para(doc.empty_message, empty))
    for sec in doc.sections:
        if sec.title:
            story.append(_para(sec.title, section))
        story.append(_table(sec.table, available))
    if doc.notes:
        story.append(Spacer(1, 8))
        for text_note in doc.notes:
            story.append(_para(text_note, note))
    template.build(story, canvasmaker=_NumberedCanvas)
    return buffer.getvalue()
