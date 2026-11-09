from datetime import UTC, datetime

from sqlalchemy.orm import DeclarativeBase


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass
