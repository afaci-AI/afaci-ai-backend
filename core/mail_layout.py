"""Оформление транзакционных писем: HTML с инлайн-стилями и текстовая версия.

Почтовые программы (Gmail, Outlook, Яндекс) режут `<style>`, внешние шрифты и
современный CSS, поэтому разметка — таблицы и стили прямо в тегах. Значения
экранируются: имя пользователя приходит из БД и может содержать `<`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from html import escape

BRAND = "#2E6BB5"  # --primary сайта, oklch(0.55 0.15 250)
TEXT = "#1F2937"
MUTED = "#6B7280"
BORDER = "#E5E7EB"
BACKGROUND = "#F3F4F6"
FONT = "-apple-system, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"


@dataclass(frozen=True)
class Email:
    """Содержимое письма; `highlight` — главное значение (код, пароль)."""

    title: str
    greeting: str
    intro: str
    highlight: str
    highlight_label: str
    notes: list[str] = field(default_factory=list)
    footer: str = ""
    preheader: str = ""


def render_text(email: Email) -> str:
    parts = [
        email.greeting,
        "",
        email.intro,
        "",
        f"{email.highlight_label}: {email.highlight}",
        "",
        *[line for note in email.notes for line in (note, "")],
    ]
    if email.footer:
        parts += [email.footer, ""]
    parts.append("— AFACI")
    return "\n".join(parts) + "\n"


def _paragraph(text: str, color: str = TEXT, size: int = 15) -> str:
    return (
        f'<p style="margin:0 0 16px;font-size:{size}px;line-height:1.55;'
        f'color:{color};">{escape(text)}</p>'
    )


def _highlight(value: str, label: str) -> str:
    # Разрядка только через letter-spacing: при копировании код вставится
    # без пробелов и подойдёт в ячейки ввода.
    return (
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        'style="margin:8px 0 24px;"><tr><td align="center">'
        f'<div style="font-size:13px;color:{MUTED};margin-bottom:8px;">'
        f"{escape(label)}</div>"
        f'<div style="display:inline-block;padding:14px 24px;border:2px solid {BRAND};'
        f"border-radius:12px;background:#F5F8FC;font-family:'SFMono-Regular',Menlo,"
        f"Consolas,monospace;font-size:34px;font-weight:700;letter-spacing:8px;"
        f'color:{TEXT};">{escape(value)}</div>'
        "</td></tr></table>"
    )


def render_html(email: Email) -> str:
    notes = "".join(_paragraph(note, MUTED, 14) for note in email.notes)
    footer = (
        f'<p style="margin:0;font-size:12px;line-height:1.5;color:{MUTED};">'
        f"{escape(email.footer)}</p>"
        if email.footer
        else ""
    )
    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(email.title)}</title>
</head>
<body style="margin:0;padding:0;background:{BACKGROUND};font-family:{FONT};">
<div style="display:none;max-height:0;overflow:hidden;opacity:0;">{escape(email.preheader)}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{BACKGROUND};padding:32px 12px;">
<tr><td align="center">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:520px;background:#FFFFFF;border:1px solid {BORDER};border-radius:14px;">
<tr><td style="padding:24px 32px;border-bottom:1px solid {BORDER};">
<span style="display:inline-block;width:32px;height:32px;line-height:32px;text-align:center;border-radius:8px;background:{BRAND};color:#FFFFFF;font-weight:700;font-size:16px;vertical-align:middle;">A</span>
<span style="margin-left:10px;font-size:18px;font-weight:700;color:{TEXT};vertical-align:middle;">AFACI</span>
</td></tr>
<tr><td style="padding:28px 32px 12px;">
<h1 style="margin:0 0 16px;font-size:22px;line-height:1.3;color:{TEXT};">{escape(email.title)}</h1>
{_paragraph(email.greeting)}
{_paragraph(email.intro)}
{_highlight(email.highlight, email.highlight_label)}
{notes}
</td></tr>
<tr><td style="padding:16px 32px 24px;border-top:1px solid {BORDER};">
{footer}
<p style="margin:8px 0 0;font-size:12px;color:{MUTED};">Письмо отправлено автоматически, отвечать на него не нужно.</p>
</td></tr>
</table>
</td></tr>
</table>
</body>
</html>
"""
