import uuid

from sqlalchemy import Boolean, Column, DateTime, Integer, String
from sqlalchemy.dialects.postgresql import UUID

from .base import Base, _utcnow


class AppVersion(Base):
    __tablename__ = "app_versions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    version = Column(String, nullable=False)
    version_code = Column(Integer, nullable=False, unique=True)
    apk_url = Column(String, nullable=False)
    apk_filename = Column(String, nullable=False)
    changelog = Column(String, nullable=True)
    force_update = Column(Boolean, nullable=False, default=False)
    min_supported_version_code = Column(Integer, nullable=True)
    is_current = Column(Boolean, nullable=False, default=True)
    published_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
