from unittest.mock import MagicMock, patch
from binance_square_bot.services.cli.followin_cli import FollowinCliService
from binance_square_bot.services.source.followin_source import FollowinTopic, FollowinToken


class TestFollowinCliServiceInit:
    """Test FollowinCliService initialization."""

    def test_followin_cli_service_init(self):
        """Test FollowinCliService can be initialized."""
        service = FollowinCliService(dry_run=True)
        assert service.dry_run is True

    def test_followin_cli_service_init_with_limit(self):
        """Test FollowinCliService can be initialized with a limit."""
        service = FollowinCliService(dry_run=False, limit=5)
        assert service.dry_run is False
        assert service.limit == 5


class TestFollowinCliServiceDeduplication:
    """Test deduplication filtering in FollowinCliService._publish_items."""

    def test_publish_items_filters_published_topics(self):
        """Test that already published topics are filtered out."""
        service = FollowinCliService(dry_run=True)

        # Mock storage.is_content_published_today to return True for item 1
        def mock_is_published(source_name, content_type, content_id):
            return content_id == "1"  # item with id=1 is already published

        service.storage.is_content_published_today = mock_is_published

        # Create test items (FollowinTopic)
        items = [
            FollowinTopic(id=1, title="Topic 1", summary="Summary 1", url="https://test1.com"),
            FollowinTopic(id=2, title="Topic 2", summary="Summary 2", url="https://test2.com"),
            FollowinTopic(id=3, title="Topic 3", summary="Summary 3", url="https://test3.com"),
        ]

        # Mock source.generate
        service.source.generate = MagicMock(return_value=["tweet1", "tweet2"])

        result = service._publish_items(items, "FollowinSourceTopics", "Trending Topics")

        # Should have filtered out 1 item, leaving 2
        assert result["items_fetched"] == 2

    def test_publish_items_filters_published_io_flow_tokens(self):
        """Test that already published IO flow tokens are filtered out."""
        service = FollowinCliService(dry_run=True)

        # Mock storage.is_content_published_today to return True for item 101
        def mock_is_published(source_name, content_type, content_id):
            return content_id == "101"

        service.storage.is_content_published_today = mock_is_published

        # Create test items (FollowinToken)
        items = [
            FollowinToken(id=101, name="Token 1", symbol="TKN1", summary="Summary 1", category="io_flow"),
            FollowinToken(id=102, name="Token 2", symbol="TKN2", summary="Summary 2", category="io_flow"),
        ]

        service.source.generate = MagicMock(return_value=["tweet1"])

        result = service._publish_items(items, "FollowinSourceIOFlow", "IO Flow Tokens")

        # Should have filtered out 1 item, leaving 1
        assert result["items_fetched"] == 1

    def test_publish_items_filters_published_discussion_tokens(self):
        """Test that already published discussion tokens are filtered out."""
        service = FollowinCliService(dry_run=True)

        # Mock storage.is_content_published_today to return True for items 201 and 202
        def mock_is_published(source_name, content_type, content_id):
            return content_id in ["201", "202"]

        service.storage.is_content_published_today = mock_is_published

        # Create test items (FollowinToken)
        items = [
            FollowinToken(id=201, name="Token A", symbol="TKNA", summary="Summary A", category="discussion"),
            FollowinToken(id=202, name="Token B", symbol="TKNB", summary="Summary B", category="discussion"),
            FollowinToken(id=203, name="Token C", symbol="TKNC", summary="Summary C", category="discussion"),
        ]

        service.source.generate = MagicMock(return_value=["tweet1"])

        result = service._publish_items(items, "FollowinSourceDiscussion", "Discussion Tokens")

        # Should have filtered out 2 items, leaving 1
        assert result["items_fetched"] == 1

    def test_publish_items_filter_before_limit(self):
        """Test that filtering happens before limit is applied."""
        service = FollowinCliService(dry_run=True, limit=2)

        # Published items: ids 1 and 2 (2 items)
        # Unpublished items: ids 3, 4, 5 (3 items)
        # After filtering: 3 items remain
        # After limit: 2 items remain
        def mock_is_published(source_name, content_type, content_id):
            return content_id in ["1", "2"]

        service.storage.is_content_published_today = mock_is_published

        items = [
            FollowinTopic(id=1, title="Topic 1", summary="Summary 1", url="https://test1.com"),
            FollowinTopic(id=2, title="Topic 2", summary="Summary 2", url="https://test2.com"),
            FollowinTopic(id=3, title="Topic 3", summary="Summary 3", url="https://test3.com"),
            FollowinTopic(id=4, title="Topic 4", summary="Summary 4", url="https://test4.com"),
            FollowinTopic(id=5, title="Topic 5", summary="Summary 5", url="https://test5.com"),
        ]

        service.source.generate = MagicMock(return_value=["tweet1", "tweet2"])

        result = service._publish_items(items, "FollowinSourceTopics", "Trending Topics")

        # 5 total - 2 filtered = 3 remaining, then limited to 2
        assert result["items_fetched"] == 2

    def test_publish_items_no_items(self):
        """Test _publish_items with empty items list."""
        service = FollowinCliService(dry_run=True)

        result = service._publish_items([], "FollowinSourceTopics", "Trending Topics")

        assert result["items_fetched"] == 0

    def test_publish_items_all_filtered_out(self):
        """Test when all items are filtered out."""
        service = FollowinCliService(dry_run=True)

        # All items are already published
        def mock_is_published(source_name, content_type, content_id):
            return True

        service.storage.is_content_published_today = mock_is_published

        items = [
            FollowinTopic(id=1, title="Topic 1", summary="Summary 1", url="https://test1.com"),
            FollowinTopic(id=2, title="Topic 2", summary="Summary 2", url="https://test2.com"),
        ]

        result = service._publish_items(items, "FollowinSourceTopics", "Trending Topics")

        # All items filtered out, returns 0 fetched
        assert result["items_fetched"] == 0
