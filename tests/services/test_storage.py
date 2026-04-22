from binance_square_bot.services.storage import StorageService

def test_daily_execution_count_flow():
    """Test execution count increment and check flow."""
    storage = StorageService(":memory:")

    source_name = "TestSource"

    # Initially 0
    assert storage.get_daily_execution_count(source_name) == 0
    assert storage.can_execute_source(source_name, 5) is True

    # Increment
    storage.increment_daily_execution(source_name)
    assert storage.get_daily_execution_count(source_name) == 1

    # Test limit
    for _ in range(4):
        storage.increment_daily_execution(source_name)
    assert storage.get_daily_execution_count(source_name) == 5
    assert storage.can_execute_source(source_name, 5) is False

def test_daily_publish_count_flow():
    """Test publish count increment per API key."""
    storage = StorageService(":memory:")

    target_name = "BinanceTarget"
    api_key = "test_api_key_1"

    # Initially 0
    assert storage.get_daily_publish_count(target_name, api_key) == 0
    assert storage.can_publish_key(target_name, api_key, 100) is True

    # Increment
    storage.increment_daily_publish_count(target_name, api_key)
    assert storage.get_daily_publish_count(target_name, api_key) == 1

    # Different API key is separate
    api_key_2 = "test_api_key_2"
    assert storage.get_daily_publish_count(target_name, api_key_2) == 0

def test_can_publish_key_with_limit():
    """Test can_publish_key correctly enforces limits."""
    storage = StorageService(":memory:")

    target_name = "BinanceTarget"
    api_key = "limit_test_key"

    # Increment up to limit
    for i in range(100):
        assert storage.can_publish_key(target_name, api_key, 100) is True
        storage.increment_daily_publish_count(target_name, api_key)

    # Now at limit
    assert storage.get_daily_publish_count(target_name, api_key) == 100
    assert storage.can_publish_key(target_name, api_key, 100) is False


def test_content_deduplication():
    """Test content deduplication functionality."""
    storage = StorageService(db_path=":memory:")

    source_name = "FnSource"
    content_type = "news"
    url = "https://example.com/article/123"

    # Should not be published initially
    assert not storage.is_content_published_today(source_name, content_type, url)

    # Mark as published
    storage.mark_content_published(source_name, content_type, url)

    # Now should be published
    assert storage.is_content_published_today(source_name, content_type, url)

    # Different URL should not be published
    assert not storage.is_content_published_today(source_name, content_type, "https://other.com")
