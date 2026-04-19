"""
@file test_polymarket_filter.py
@description Tests for PolymarketFilter service
@created-by fullstack-dev-workflow
"""

from binance_square_bot.models.polymarket_market import PolymarketMarket, TokenInfo
from binance_square_bot.services.polymarket_filter import PolymarketFilter


def create_test_market(question: str, condition_id: str, volume: float, created_at: int, yes_price: float) -> PolymarketMarket:
    """Create a test PolymarketMarket instance with given parameters."""
    return PolymarketMarket(
        condition_id=condition_id,
        question=question,
        tokens=[
            TokenInfo(token_id="t1", outcome="YES", price=yes_price),
            TokenInfo(token_id="t2", outcome="NO", price=1.0 - yes_price),
        ],
        volume=volume,
        created_at=created_at,
    )


def test_filter_min_volume():
    """Test that markets below minimum volume are correctly filtered out."""
    filterer = PolymarketFilter(min_volume=1000)
    market_low = create_test_market("Low vol", "0x1", 500, 1713500000, 0.75)
    market_high = create_test_market("High vol", "0x2", 5000, 1713500000, 0.75)

    filtered = filterer.filter_min_volume([market_low, market_high])
    assert len(filtered) == 1
    assert filtered[0].condition_id == "0x2"


def test_select_best_markets():
    """Test that the highest scoring markets are correctly selected."""
    from datetime import datetime
    current_ts = int(datetime.now().timestamp())
    yesterday = current_ts - 3600 * 24

    # New interesting market should be selected (0.75 is between 0.6 and 0.9)
    # Interesting probability gives bonus score
    markets = [
        create_test_market("Old normal", "0x1", 10000, yesterday - 3600 * 48, 0.5),
        create_test_market("New interesting", "0x2", 5000, yesterday, 0.75),  # interesting + new
        create_test_market("New normal", "0x3", 1000, yesterday, 0.5),
    ]

    filterer = PolymarketFilter(min_volume=1000)
    top = filterer.select_best_markets(markets)
    assert len(top) > 0
    assert top[0].condition_id == "0x2"
    assert top[0].is_probability_extreme() is True


def test_already_published_excluded():
    """Test that already published markets are correctly excluded from selection."""
    from datetime import datetime
    current_ts = int(datetime.now().timestamp())
    # 0.75 is interesting probability that gives higher score
    markets = [
        create_test_market("A", "0x1", 10000, current_ts, 0.75),
        create_test_market("B", "0x2", 5000, current_ts, 0.70),  # 70% YES, meets 60-90 criteria
    ]

    filterer = PolymarketFilter(min_volume=1000, published_ids={"0x1"})
    top = filterer.select_best_markets(markets)
    assert len(top) > 0
    assert top[0].condition_id == "0x2"


def test_select_best_markets_empty_input():
    """Test that empty list is returned when input is an empty list."""
    filterer = PolymarketFilter(min_volume=1000)
    top = filterer.select_best_markets([])
    assert len(top) == 0


def test_select_best_markets_all_below_min_volume():
    """Test that empty list is returned when all markets have volume below minimum threshold."""
    from datetime import datetime
    current_ts = int(datetime.now().timestamp())
    # All markets below 1000 min volume
    markets = [
        create_test_market("Low 1", "0x1", 100, current_ts, 0.5),
        create_test_market("Low 2", "0x2", 500, current_ts, 0.15),
        create_test_market("Low 3", "0x3", 999, current_ts, 0.75),
    ]

    filterer = PolymarketFilter(min_volume=1000)
    top = filterer.select_best_markets(markets)
    assert len(top) == 0


def test_filter_min_volume_volume_none():
    """Test that markets with None volume are correctly filtered out."""
    from datetime import datetime
    current_ts = int(datetime.now().timestamp())
    # Create a market with None volume (treats as 0)
    market_none = PolymarketMarket(
        condition_id="0x1",
        question="No volume",
        tokens=[
            TokenInfo(token_id="t1", outcome="YES", price=0.75),
            TokenInfo(token_id="t2", outcome="NO", price=0.25),
        ],
        volume=None,
        created_at=current_ts,
    )
    market_valid = create_test_market("Has volume", "0x2", 2000, current_ts, 0.75)

    filterer = PolymarketFilter(min_volume=1000)
    filtered = filterer.filter_min_volume([market_none, market_valid])
    # None volume market should be filtered out, only valid remains
    assert len(filtered) == 1
    assert filtered[0].condition_id == "0x2"


def test_filter_win_rate_range():
    """Test filter_win_rate_range correctly filters markets where either outcome is 60%-90%."""
    from datetime import datetime
    current_ts = int(datetime.now().timestamp())

    filterer = PolymarketFilter(min_volume=1000)

    # Test 1: YES price 70% (in range) → should be kept
    market_yes_in = create_test_market("YES 70%", "t1", 1000, current_ts, 0.70)
    # Test 2: YES 50%, NO 50% → neither in range → should be filtered
    market_equal = create_test_market("50-50", "t2", 1000, current_ts, 0.50)
    # Test 3: YES 25%, NO 75% → NO is in range → should be kept
    market_no_in = PolymarketMarket(
        condition_id="t3",
        question="YES 25 NO 75",
        tokens=[
            TokenInfo(token_id="t1", outcome="YES", price=0.25),
            TokenInfo(token_id="t2", outcome="NO", price=0.75),
        ],
        volume=1000,
        created_at=current_ts,
    )
    # Test 4: YES exactly 60% → not > 60 → should be filtered
    market_exact_min = create_test_market("YES exactly 60", "t4", 1000, current_ts, 0.60)
    # Test 5: YES exactly 90% → not < 90 → should be filtered
    market_exact_max = create_test_market("YES exactly 90", "t5", 1000, current_ts, 0.90)
    # Test 6: YES 95% → NO 5% → neither in range → should be filtered
    market_too_extreme = create_test_market("YES 95%", "t6", 1000, current_ts, 0.95)

    all_markets = [market_yes_in, market_equal, market_no_in, market_exact_min, market_exact_max, market_too_extreme]
    filtered = filterer.filter_win_rate_range(all_markets)

    # Should keep 2 markets: one with YES in range, one with NO in range
    assert len(filtered) == 2
    kept_ids = {m.condition_id for m in filtered}
    assert "t1" in kept_ids
    assert "t3" in kept_ids
