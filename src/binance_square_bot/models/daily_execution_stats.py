from sqlalchemy import Column, String, Integer, DateTime
from datetime import datetime
from .base import Base

class DailyExecutionStatsModel(Base):
    __tablename__ = "daily_execution_stats"

    source_name = Column(String, primary_key=True, index=True)
    date = Column(String, primary_key=True, index=True)  # YYYY-MM-DD
    count = Column(Integer, default=0)
    last_executed_at = Column(DateTime)

    @classmethod
    def today(cls) -> str:
        return datetime.now().strftime("%Y-%m-%d")

    def can_execute(self, max_executions: int) -> bool:
        return self.count < max_executions
