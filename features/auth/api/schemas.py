"""Схемы запросов аутентификации."""

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    email: str
    password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=6)


class PasswordResetRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)


class PasswordResetVerify(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    code: str = Field(pattern=r"^\s*\d{6}\s*$")


class PasswordResetConfirm(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    code: str = Field(pattern=r"^\s*\d{6}\s*$")
    new_password: str = Field(min_length=6, max_length=128)
