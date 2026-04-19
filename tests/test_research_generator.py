from unittest.mock import Mock, patch
from binance_square_bot.models.polymarket_market import PolymarketMarket, TokenInfo
from binance_square_bot.services.research_generator import ResearchGenerator
from binance_square_bot.config import config


def test_build_prompt():
    market = PolymarketMarket(
        condition_id="0x123",
        question="Will BTC exceed $100,000 by December 2025?",
        description="Bitcoin price prediction question",
        tokens=[
            TokenInfo(token_id="t1", outcome="YES", price=0.35),
            TokenInfo(token_id="t2", outcome="NO", price=0.65),
        ],
        volume=100000.0,
        created_at=1713500000,
    )

    generator = ResearchGenerator()
    prompt = generator.build_prompt(market)

    assert "Will BTC exceed $100,000" in prompt
    assert "35.0%" in prompt
    assert "65.0%" in prompt
    assert "100000" in prompt
    assert "币安广场" in prompt
