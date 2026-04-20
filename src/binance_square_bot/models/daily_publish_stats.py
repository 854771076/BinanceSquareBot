from sqlalchemy import Column, String, Integer, DateTime
from datetime import datetime
import hashlib
from .base import Base

class DailyPublishStatsModel(Base):
    __tablename__ = "daily_publish_stats"

    target_name = Column(String, primary_key=True, index=True)
    api_key_hash = Column(String, primary_key=True, index=True)  # Hash API key for privacy
    api_key_mask = Column(String)                                  # Masked for display (e.g., "xxxx...abcd")
    date = Column(String, primary_key=True, index=True)           # YYYY-MM-DD
    count = Column(Integer, default=0)
    last_published_at = Column(DateTime)

    @classmethod
    def today(cls) -> str:
        return datetime.now().strftime("%Y-%m-%d")

    @classmethod
    def hash_key(cls, api_key: str) -> str:
        """Hash API key for indexing - returns first 16 hex chars of SHA256."""
        return hashlib.sha256(api_key.encode()).hexdigest()[:16]

    @classmethod
    def mask_key(cls, api_key: str) -> str:
        """Mask API key for display - shows first 4 and last 4 chars."""
        if len(api_key) <= 8:
            return api_key
        return f"{api_key[:4]}...{api_key[-4:]}"
