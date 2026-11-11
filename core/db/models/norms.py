import uuid

from sqlalchemy import (
    CheckConstraint,
    Column,
    Double,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID

from .base import Base

SOURCE_KINDS = ("article", "document", "book", "link", "file")


class Source(Base):
    """Источник информации: документ, статья, книга или ссылка."""

    __tablename__ = "sources"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    kind = Column(String, nullable=False)
    title = Column(Text, nullable=False)
    authors = Column(Text, nullable=True)
    year = Column(Integer, nullable=True)
    location = Column(Text, nullable=True)
    url = Column(Text, nullable=True)
    pdf_filename = Column(String, nullable=True)
    used_for = Column(Text, nullable=True)
    sort_order = Column(Integer, nullable=False, default=0)

    __table_args__ = (
        CheckConstraint(
            "kind IN ('article', 'document', 'book', 'link', 'file')",
            name="ck_sources_kind",
        ),
    )


class DailyNorm(Base):
    """Усреднённая суточная норма нутриента со ссылкой на источник."""

    __tablename__ = "daily_norms"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key = Column(String, nullable=False, unique=True)
    name = Column(String, nullable=False)
    unit = Column(String, nullable=False)
    value = Column(Double, nullable=False)
    source_id = Column(UUID(as_uuid=True), ForeignKey("sources.id"), nullable=False)
    basis = Column(Text, nullable=True)
    sort_order = Column(Integer, nullable=False, default=0)
