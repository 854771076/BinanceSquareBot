from sqlalchemy import Column, String, DateTime
from datetime import datetime
import hashlib
from .base import Base


class PublishedContentModel(Base):
    __tablename__ = "published_content"

    content_hash = Column(String(64), primary_key=True)
    source_name = Column(String(100), primary_key=True, index=True)
    content_type = Column(String(50), primary_key=True, index=True)
    date = Column(String(20), primary_key=True, index=True)
    published_at = Column(DateTime)

    @classmethod
    def today(cls) -> str:
        return datetime.now().strftime("%Y-%m-%d")

    @classmethod
    def hash_content(cls, content_identifier: str) -> str:
        """Hash URL or ID for indexing - returns full SHA256 hex."""
        return hashlib.sha256(content_identifier.encode()).hexdigest()
