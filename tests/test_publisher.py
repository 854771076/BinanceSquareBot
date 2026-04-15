"""
@file test_publisher.py
@description 发布服务单元测试
@design-doc docs/01-architecture/system-architecture.md
@task-id BE-09
@created-by fullstack-dev-workflow
"""

from unittest.mock import Mock, patch
from datetime import datetime

from src.binance_square_bot.services.publisher import PublishResult, PublisherService
from src.binance_square_bot.models.tweet import Tweet


def test_publish_result_success():
    """测试成功发布结果"""
    result = PublishResult(success=True, tweet_id="12345")
    assert result.success
    assert result.tweet_id == "12345"
    assert result.tweet_url == "https://www.binance.com/square/post/12345"
    assert result.error_message == ""


def test_publish_result_failure():
    """测试失败发布结果"""
    result = PublishResult(success=False, error_message="API error")
    assert not result.success
    assert result.tweet_id is None
    assert result.tweet_url is None
    assert result.error_message == "API error"


def test_publish_result_no_tweet_id():
    """测试成功但没有tweet_id"""
    result = PublishResult(success=True, tweet_id=None)
    assert result.success
    assert result.tweet_url is None


def test_publish_tweet_success():
    """测试发布推文成功场景"""
    # 创建测试tweet
    tweet = Tweet(
        content="测试推文内容 #BTC $BTC",
        article_url="https://example.com/news/1",
        generated_at=datetime.now(),
        validation_passed=True,
    )

    publisher = PublisherService()

    # mock httpx response
    mock_response = Mock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {
        "code": "000000",
        "message": "success",
        "data": {"id": "123456"}
    }

    with patch.object(publisher.client, 'post', return_value=mock_response):
        result = publisher.publish_tweet("test-api-key", tweet)

        assert result.success
        assert result.tweet_id == "123456"
        assert result.tweet_url == "https://www.binance.com/square/post/123456"


def test_publish_tweet_api_error():
    """测试API返回错误码"""
    tweet = Tweet(
        content="测试推文内容 #BTC $BTC",
        article_url="https://example.com/news/1",
        generated_at=datetime.now(),
        validation_passed=True,
    )

    publisher = PublisherService()

    mock_response = Mock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {
        "code": "100001",
        "message": "Invalid API key",
    }

    with patch.object(publisher.client, 'post', return_value=mock_response):
        result = publisher.publish_tweet("wrong-key", tweet)

        assert not result.success
        assert "Invalid API key" in result.error_message


def test_publish_tweet_http_error():
    """测试HTTP错误"""
    tweet = Tweet(
        content="测试推文内容 #BTC $BTC",
        article_url="https://example.com/news/1",
        generated_at=datetime.now(),
        validation_passed=True,
    )

    publisher = PublisherService()

    with patch.object(publisher.client, 'post') as mock_post:
        mock_post.side_effect = Exception("Network error")

        result = publisher.publish_tweet("test-api-key", tweet)

        assert not result.success
        assert "Network error" in result.error_message


def test_publish_tweet_numeric_success_code():
    """测试数字形式的成功code"""
    tweet = Tweet(
        content="测试推文内容 #BTC $BTC",
        article_url="https://example.com/news/1",
        generated_at=datetime.now(),
        validation_passed=True,
    )

    publisher = PublisherService()

    mock_response = Mock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {
        "code": 0,
        "message": "success",
        "data": {"id": 789012},
    }

    with patch.object(publisher.client, 'post', return_value=mock_response):
        result = publisher.publish_tweet("test-api-key", tweet)

        assert result.success
        assert result.tweet_id == "789012"
