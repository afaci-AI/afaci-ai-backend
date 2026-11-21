"""Временный пароль нового пользователя и письмо с данными для входа."""

from __future__ import annotations

import os
import secrets
from datetime import timedelta

from core.mail_layout import Email

TEMP_PASSWORD_TTL = timedelta(hours=72)
TEMP_PASSWORD_LENGTH = 10
# Без похожих символов (0/O, 1/l/I), чтобы пароль было легко перепечатать.
ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789"
DIGITS = "23456789"

SUBJECT = "AFACI: данные для входа"


def generate_temp_password(length: int = TEMP_PASSWORD_LENGTH) -> str:
    """Случайный пароль, в котором есть и буквы, и цифры."""
    while True:
        password = "".join(secrets.choice(ALPHABET) for _ in range(length))
        if any(c in DIGITS for c in password) and any(c.isalpha() for c in password):
            return password


def login_hint() -> str:
    """Где входить: адрес сайта из APP_PUBLIC_URL, если он задан."""
    url = os.getenv("APP_PUBLIC_URL", "").strip().rstrip("/")
    if url:
        return f"Войдите в мобильном приложении AFACI или на сайте {url}/login."
    return "Войдите в мобильном приложении AFACI или на сайте AFACI."


def welcome_email(name: str, email: str, password: str) -> Email:
    hours = int(TEMP_PASSWORD_TTL.total_seconds() // 3600)
    return Email(
        title="Добро пожаловать в AFACI",
        greeting=f"Здравствуйте, {name}!",
        intro=f"Администратор создал для вас учётную запись. Логин: {email}. "
        f"{login_hint()}",
        highlight=password,
        highlight_label="Временный пароль",
        notes=[
            (
                "При первом входе система попросит задать собственный пароль — "
                "до этого остальные разделы недоступны."
            ),
            (
                f"Временный пароль действует {hours} часа. Если срок истёк, "
                "попросите администратора выслать новый."
            ),
        ],
        footer="Если вы не ожидали это письмо, просто проигнорируйте его.",
        preheader=f"Логин: {email}",
    )
