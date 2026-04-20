from pydantic import BaseModel
from binance_square_bot.services.source.fn_source import FnSource, Article

def test_article_model():
    """Test Article model validation."""
    article = Article(
        title="Test Title",
        url="https://test.com",
        content="Test content"
    )
    assert article.title == "Test Title"
    assert article.url == "https://test.com"
    assert article.content == "Test content"

def test_fn_source_config():
    """Test FnSource has correct config fields."""
    assert "base_url" in FnSource.Config.model_fields
    assert "timeout" in FnSource.Config.model_fields
    assert "enabled" in FnSource.Config.model_fields
    assert "daily_max_executions" in FnSource.Config.model_fields
