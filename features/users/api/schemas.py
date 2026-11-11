"""Схемы запросов управления пользователями."""

from datetime import datetime

from pydantic import BaseModel, Field


class UserCreateRequest(BaseModel):
    email: str = Field(min_length=3)
    name: str = Field(min_length=1)
    password: str = Field(min_length=6)
    role: str = "viewer"
    access_expires_at: datetime | None = None
    must_change_password: bool = False


class UserUpdateRequest(BaseModel):
    name: str | None = None
    role: str | None = None
    is_active: bool | None = None
    access_expires_at: datetime | None = None
    access_expires_at_unlimited: bool | None = None  # True — сбросить срок в null
