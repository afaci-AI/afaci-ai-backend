"""Схемы ответов норм и источников."""

from pydantic import BaseModel


class SourceOut(BaseModel):
    id: str
    kind: str
    title: str
    authors: str | None = None
    year: int | None = None
    location: str | None = None
    url: str | None = None
    pdf_url: str | None = None
    used_for: str | None = None


class NormRowOut(BaseModel):
    key: str
    name: str
    unit: str
    norm: float
    amount: float | None = None
    percent: float | None = None
    source_id: str | None = None
    basis: str | None = None


class NormsInfoOut(BaseModel):
    title: str
    paragraphs: list[str]
    disclaimer: str


class DailyNormsOut(BaseModel):
    norms: list[NormRowOut]
    sources: list[SourceOut]
    info: NormsInfoOut
