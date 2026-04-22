from unittest.mock import patch, MagicMock
from binance_square_bot.services.cli.fn_cli import FnCliService


def test_fn_cli_service_init():
    """Test FnCliService can be initialized."""
    service = FnCliService(dry_run=True, limit=5)
    assert service.dry_run is True
    assert service.limit == 5


class MockArticle:
    """Mock Article class for testing."""
    def __init__(self, url):
        self.url = url


class MockEvent:
    """Mock Event class for testing."""
    def __init__(self, url):
        self.url = url


def test_execute_filter_out_already_published():
    """Test that already published articles are filtered out."""
    service = FnCliService(dry_run=True, limit=10)

    # Create mock articles
    article1 = MockArticle("https://example.com/article1")
    article2 = MockArticle("https://example.com/article2")
    article3 = MockArticle("https://example.com/article3")

    # Mock the storage to return True for article2 (already published)
    def mock_is_content_published(source, content_type, url):
        return url == "https://example.com/article2"

    with patch.object(service.storage, 'is_content_published_today', side_effect=mock_is_content_published):
        with patch.object(service.source, 'fetch', return_value=[article1, article2, article3]):
            with patch.object(service.source, 'generate', return_value=["tweet1", "tweet3"]):
                with patch.object(service.storage, 'can_execute_source', return_value=True):
                    result = service.execute()

    # Should have filtered out 1 article, leaving 2
    assert result["articles_fetched"] == 2
    assert len(result["tweets_generated"]) == 2


def test_execute_calendar_filter_out_already_published():
    """Test that already published calendar events are filtered out."""
    service = FnCliService(dry_run=True, limit=10)

    event1 = MockEvent("https://example.com/event1")
    event2 = MockEvent("https://example.com/event2")

    def mock_is_content_published(source, content_type, url):
        return url == "https://example.com/event1"

    with patch.object(service.storage, 'is_content_published_today', side_effect=mock_is_content_published):
        with patch.object(service.source, 'fetch_calendar', return_value=[event1, event2]):
            with patch.object(service.source, 'generate_calendar', return_value=["tweet2"]):
                with patch.object(service.storage, 'can_execute_source', return_value=True):
                    result = service.execute_calendar()

    assert result["events_fetched"] == 1
    assert len(result["tweets_generated"]) == 1


def test_execute_airdrops_filter_out_already_published():
    """Test that already published airdrop events are filtered out."""
    service = FnCliService(dry_run=True, limit=10)

    event1 = MockEvent("https://example.com/airdrop1")
    event2 = MockEvent("https://example.com/airdrop2")

    def mock_is_content_published(source, content_type, url):
        return url == "https://example.com/airdrop1"

    with patch.object(service.storage, 'is_content_published_today', side_effect=mock_is_content_published):
        with patch.object(service.source, 'fetch_airdrops', return_value=[event1, event2]):
            with patch.object(service.source, 'generate_airdrops', return_value=["tweet2"]):
                with patch.object(service.storage, 'can_execute_source', return_value=True):
                    result = service.execute_airdrops()

    assert result["events_fetched"] == 1
    assert len(result["tweets_generated"]) == 1


def test_execute_fundraising_filter_out_already_published():
    """Test that already published fundraising events are filtered out."""
    service = FnCliService(dry_run=True, limit=10)

    event1 = MockEvent("https://example.com/fund1")
    event2 = MockEvent("https://example.com/fund2")

    def mock_is_content_published(source, content_type, url):
        return url == "https://example.com/fund1"

    with patch.object(service.storage, 'is_content_published_today', side_effect=mock_is_content_published):
        with patch.object(service.source, 'fetch_fundraising', return_value=[event1, event2]):
            with patch.object(service.source, 'generate_fundraising', return_value=["tweet2"]):
                with patch.object(service.storage, 'can_execute_source', return_value=True):
                    result = service.execute_fundraising()

    assert result["events_fetched"] == 1
    assert len(result["tweets_generated"]) == 1


def test_filter_content_type_parameters():
    """Test that correct content_type parameters are passed to storage."""
    service = FnCliService(dry_run=True, limit=10)

    article = MockArticle("https://example.com/article")

    call_args = []

    def mock_is_content_published(source, content_type, url):
        call_args.append((source, content_type))
        return False

    # Test news
    call_args.clear()
    with patch.object(service.storage, 'is_content_published_today', side_effect=mock_is_content_published):
        with patch.object(service.source, 'fetch', return_value=[article]):
            with patch.object(service.source, 'generate', return_value=["tweet"]):
                with patch.object(service.storage, 'can_execute_source', return_value=True):
                    service.execute()
    assert call_args == [("FnSource", "news")]

    # Test calendar
    call_args.clear()
    with patch.object(service.storage, 'is_content_published_today', side_effect=mock_is_content_published):
        with patch.object(service.source, 'fetch_calendar', return_value=[MockEvent("e1")]):
            with patch.object(service.source, 'generate_calendar', return_value=["t"]):
                with patch.object(service.storage, 'can_execute_source', return_value=True):
                    service.execute_calendar()
    assert call_args == [("FnSource", "calendar")]

    # Test airdrop
    call_args.clear()
    with patch.object(service.storage, 'is_content_published_today', side_effect=mock_is_content_published):
        with patch.object(service.source, 'fetch_airdrops', return_value=[MockEvent("e1")]):
            with patch.object(service.source, 'generate_airdrops', return_value=["t"]):
                with patch.object(service.storage, 'can_execute_source', return_value=True):
                    service.execute_airdrops()
    assert call_args == [("FnSource", "airdrop")]

    # Test fundraising
    call_args.clear()
    with patch.object(service.storage, 'is_content_published_today', side_effect=mock_is_content_published):
        with patch.object(service.source, 'fetch_fundraising', return_value=[MockEvent("e1")]):
            with patch.object(service.source, 'generate_fundraising', return_value=["t"]):
                with patch.object(service.storage, 'can_execute_source', return_value=True):
                    service.execute_fundraising()
    assert call_args == [("FnSource", "fundraising")]


def test_mark_content_published_after_successful_publish():
    """Test that content is marked as published after successful publish."""
    service = FnCliService(dry_run=False, limit=10)

    # Create mock article
    article = MockArticle("https://example.com/test-article")

    # Mock API key configuration
    original_api_keys = service.target.config.api_keys
    service.target.config.api_keys = ["test_api_key"]

    # Track calls to mark_content_published
    marked_content = []

    def mock_mark_published(source_name, content_type, content_identifier):
        marked_content.append((source_name, content_type, content_identifier))

    with patch.object(service.storage, 'mark_content_published', side_effect=mock_mark_published):
        with patch.object(service.storage, 'can_publish_key', return_value=True):
            with patch.object(service.storage, 'can_execute_source', return_value=True):
                with patch.object(service.storage, 'increment_daily_publish_count'):
                    with patch.object(service.storage, 'increment_daily_execution'):
                        with patch.object(service.storage, 'is_content_published_today', return_value=False):
                            with patch.object(service.source, 'fetch', return_value=[article]):
                                with patch.object(service.source, 'generate', return_value=["test tweet content"]):
                                    with patch.object(service.target, 'filter', return_value="filtered tweet"):
                                        with patch.object(service.target, 'publish', return_value=(True, None)):
                                            service.execute()

    # Verify mark_content_published was called with correct parameters
    assert len(marked_content) == 1
    assert marked_content[0] == ("FnSource", "news", "https://example.com/test-article")

    # Restore original config
    service.target.config.api_keys = original_api_keys
