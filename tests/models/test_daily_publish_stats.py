from binance_square_bot.models.base import Database
from binance_square_bot.models.daily_publish_stats import DailyPublishStatsModel

def test_today_date_format():
    """Test today() returns YYYY-MM-DD format."""
    date_str = DailyPublishStatsModel.today()
    assert len(date_str) == 10
    assert date_str[4] == "-"
    assert date_str[7] == "-"

def test_api_key_hashing():
    """Test API key hashing produces consistent short hash."""
    key = "test_api_key_12345"
    hash1 = DailyPublishStatsModel.hash_key(key)
    hash2 = DailyPublishStatsModel.hash_key(key)
    assert hash1 == hash2
    assert len(hash1) == 16  # 16 hex chars from sha256

def test_api_key_masking():
    """Test API key masking hides middle portion."""
    key = "abcdefghijklmnop"
    masked = DailyPublishStatsModel.mask_key(key)
    assert masked.startswith("abcd")
    assert masked.endswith("mnop")
    assert "..." in masked

    # Short keys not masked
    short_key = "abcd"
    assert DailyPublishStatsModel.mask_key(short_key) == short_key

def test_model_persistence():
    """Test model can be saved and queried by api_key_hash."""
    Database.init(":memory:")

    api_key = "binance_test_key"
    key_hash = DailyPublishStatsModel.hash_key(api_key)

    with Database.get_session() as session:
        stat = DailyPublishStatsModel(
            target_name="BinanceTarget",
            api_key_hash=key_hash,
            api_key_mask=DailyPublishStatsModel.mask_key(api_key),
            date=DailyPublishStatsModel.today(),
            count=5
        )
        session.add(stat)
        session.commit()

        result = session.query(DailyPublishStatsModel).filter_by(
            target_name="BinanceTarget",
            api_key_hash=key_hash
        ).first()
        assert result.count == 5
        assert "..." in result.api_key_mask
