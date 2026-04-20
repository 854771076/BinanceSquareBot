from binance_square_bot.services.target.binance_target import BinanceTarget

def test_binance_target_config():
    """Test BinanceTarget has correct config fields."""
    assert "api_keys" in BinanceTarget.Config.model_fields
    assert "api_url" in BinanceTarget.Config.model_fields
    assert "enabled" in BinanceTarget.Config.model_fields
    assert "daily_max_posts_per_key" in BinanceTarget.Config.model_fields

def test_filter_passthrough():
    """Test default filter passes through content."""
    target = BinanceTarget()
    assert target.filter("test content") == "test content"
