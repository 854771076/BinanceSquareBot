from binance_square_bot.models.base import Database
from binance_square_bot.models.daily_execution_stats import DailyExecutionStatsModel
from binance_square_bot.models.daily_publish_stats import DailyPublishStatsModel
from datetime import datetime
from loguru import logger

class StorageService:
    """Service for managing persistent storage."""

    def __init__(self, db_path: str = None):
        """Initialize storage service.

        Args:
            db_path: Optional path to SQLite database file. Uses config.sqlite_db_path if None.
        """
        from ..config import config
        path = db_path if db_path else config.sqlite_db_path
        Database.init(path)
        logger.debug(f"Storage initialized with database: {path}")

    # ===== Source Execution Limits =====

    def get_daily_execution_count(self, source_name: str) -> int:
        """Get execution count for a source today."""
        with Database.get_session() as session:
            stat = session.query(DailyExecutionStatsModel).filter(
                DailyExecutionStatsModel.source_name == source_name,
                DailyExecutionStatsModel.date == DailyExecutionStatsModel.today()
            ).first()
            return stat.count if stat else 0

    def increment_daily_execution(self, source_name: str) -> None:
        """Increment execution count for a source today."""
        with Database.get_session() as session:
            stat = session.query(DailyExecutionStatsModel).filter(
                DailyExecutionStatsModel.source_name == source_name,
                DailyExecutionStatsModel.date == DailyExecutionStatsModel.today()
            ).first()

            if stat:
                stat.count += 1
                stat.last_executed_at = datetime.now()
            else:
                stat = DailyExecutionStatsModel(
                    source_name=source_name,
                    date=DailyExecutionStatsModel.today(),
                    count=1,
                    last_executed_at=datetime.now()
                )
                session.add(stat)
            session.commit()
        logger.debug(f"Incremented execution count for {source_name}")

    def can_execute_source(self, source_name: str, max_executions: int) -> bool:
        """Check if a source can execute today."""
        return self.get_daily_execution_count(source_name) < max_executions

    # ===== Target Publish Limits (Per API Key) =====

    def get_daily_publish_count(self, target_name: str, api_key: str) -> int:
        """Get publish count for a target + API key combination today."""
        key_hash = DailyPublishStatsModel.hash_key(api_key)
        with Database.get_session() as session:
            stat = session.query(DailyPublishStatsModel).filter(
                DailyPublishStatsModel.target_name == target_name,
                DailyPublishStatsModel.api_key_hash == key_hash,
                DailyPublishStatsModel.date == DailyPublishStatsModel.today()
            ).first()
            return stat.count if stat else 0

    def increment_daily_publish_count(self, target_name: str, api_key: str) -> None:
        """Increment publish count for a target + API key combination today."""
        key_hash = DailyPublishStatsModel.hash_key(api_key)
        key_mask = DailyPublishStatsModel.mask_key(api_key)

        with Database.get_session() as session:
            stat = session.query(DailyPublishStatsModel).filter(
                DailyPublishStatsModel.target_name == target_name,
                DailyPublishStatsModel.api_key_hash == key_hash,
                DailyPublishStatsModel.date == DailyPublishStatsModel.today()
            ).first()

            if stat:
                stat.count += 1
                stat.last_published_at = datetime.now()
            else:
                stat = DailyPublishStatsModel(
                    target_name=target_name,
                    api_key_hash=key_hash,
                    api_key_mask=key_mask,
                    date=DailyPublishStatsModel.today(),
                    count=1,
                    last_published_at=datetime.now()
                )
                session.add(stat)
            session.commit()
        logger.debug(f"Incremented publish count for {target_name} key {key_mask}")

    def can_publish_key(self, target_name: str, api_key: str, max_posts: int) -> bool:
        """Check if a target + API key combination can publish today."""
        return self.get_daily_publish_count(target_name, api_key) < max_posts

    # ===== Content Deduplication =====

    def is_content_published_today(
        self,
        source_name: str,
        content_type: str,
        content_identifier: str,
    ) -> bool:
        """Check if content (URL or ID) was published today."""
        from binance_square_bot.models.published_content import PublishedContentModel

        content_hash = PublishedContentModel.hash_content(content_identifier)
        date = PublishedContentModel.today()

        with Database.get_session() as session:
            exists = session.query(PublishedContentModel).filter(
                PublishedContentModel.content_hash == content_hash,
                PublishedContentModel.source_name == source_name,
                PublishedContentModel.content_type == content_type,
                PublishedContentModel.date == date,
            ).first()
            return exists is not None

    def mark_content_published(
        self,
        source_name: str,
        content_type: str,
        content_identifier: str,
    ) -> None:
        """Mark content as published today."""
        from binance_square_bot.models.published_content import PublishedContentModel
        from datetime import datetime

        content_hash = PublishedContentModel.hash_content(content_identifier)
        date = PublishedContentModel.today()

        with Database.get_session() as session:
            # Check if already exists
            exists = session.query(PublishedContentModel).filter(
                PublishedContentModel.content_hash == content_hash,
                PublishedContentModel.source_name == source_name,
                PublishedContentModel.content_type == content_type,
                PublishedContentModel.date == date,
            ).first()

            if exists:
                return

            record = PublishedContentModel(
                content_hash=content_hash,
                source_name=source_name,
                content_type=content_type,
                date=date,
                published_at=datetime.now(),
            )
            session.add(record)
            session.commit()

    # ===== Legacy URL Processing (for backward compatibility) =====

    def is_url_processed(self, url: str) -> bool:
        """Check if URL has been processed (legacy method stub)."""
        # TODO: Implement if needed for backward compatibility
        return False

    def mark_url_processed(self, url: str, processed: bool = True) -> None:
        """Mark URL as processed (legacy method stub)."""
        # TODO: Implement if needed for backward compatibility
        pass
