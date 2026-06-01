import pytest

from binance_square_bot.services.source import polymarket_source as polymarket_module
from binance_square_bot.services.source.polymarket_source import (
    PolymarketMarket,
    PolymarketSource,
)


def test_market_model():
    """Test PolymarketMarket model validation."""
    market = PolymarketMarket(
        condition_id="0x123",
        question="Will BTC reach 100k?",
        yes_price=0.75,
        no_price=0.25,
        volume=100000.0
    )
    assert market.condition_id == "0x123"
    assert market.yes_price == 0.75


def test_polymarket_source_config():
    """Test PolymarketSource has correct config fields."""
    assert "host" in PolymarketSource.Config.model_fields
    assert "min_volume_threshold" in PolymarketSource.Config.model_fields
    assert "min_win_rate" in PolymarketSource.Config.model_fields
    assert "max_win_rate" in PolymarketSource.Config.model_fields


def test_polymarket_source_constructs_without_llm_api_key(monkeypatch):
    """PolymarketSource construction must not initialize source-level LLM."""
    monkeypatch.delenv("LLM_API_KEY", raising=False)

    def fail_if_called(*args, **kwargs):
        raise AssertionError(
            "PolymarketSource constructor should not create ChatOpenAI"
        )

    monkeypatch.setattr(polymarket_module, "ChatOpenAI", fail_if_called, raising=False)

    source = PolymarketSource()

    assert source.client is not None
    assert not hasattr(source, "llm")


def test_polymarket_generate_is_deprecated_stub(monkeypatch):
    """Legacy Polymarket generation should point callers to DeepAgents."""

    class FailIfInvokedLLM:
        def invoke(self, *args, **kwargs):
            raise AssertionError("Deprecated Polymarket generation should not call LLM")

    monkeypatch.setattr(
        polymarket_module,
        "ChatOpenAI",
        lambda *args, **kwargs: FailIfInvokedLLM(),
        raising=False,
    )
    source = PolymarketSource()
    market = PolymarketMarket(
        condition_id="0x123",
        question="Will BTC reach 100k?",
        yes_price=0.75,
        no_price=0.25,
        volume=100000.0,
    )

    with pytest.raises(
        RuntimeError,
        match="DeepAgentTweetGenerator.*TweetSourceItem",
    ):
        source.generate([market])
