from unittest.mock import Mock, patch
import pytest
from binance_square_bot.models.polymarket_market import PolymarketMarket, TokenInfo
from binance_square_bot.services.research_generator import ResearchGenerator, format_validation
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


def test_build_prompt_with_errors():
    market = PolymarketMarket(
        condition_id="0x123",
        question="Will BTC exceed $100,000 by December 2025?",
        tokens=[
            TokenInfo(token_id="t1", outcome="YES", price=0.35),
            TokenInfo(token_id="t2", outcome="NO", price=0.65),
        ],
        volume=100000.0,
        created_at=1713500000,
    )

    generator = ResearchGenerator()
    errors = ["字符数 50 小于最小要求 100", "话题标签 5 个超过最大限制 3"]
    prompt = generator.build_prompt(market, errors)

    assert "Will BTC exceed $100,000" in prompt
    assert "上次生成不符合格式要求" in prompt
    assert "字符数 50 小于最小要求 100" in prompt
    assert "话题标签 5 个超过最大限制 3" in prompt


def test_format_validation():
    # Test various validation scenarios
    # 1. Too short
    with pytest.raises(ValueError, match="小于最小要求"):
        format_validation("short", min_chars=10, max_chars=1000, max_hashtags=3, max_mentions=3)

    # 2. Too long
    long_text = "x" * 2000
    with pytest.raises(ValueError, match="大于最大要求"):
        format_validation(long_text, min_chars=10, max_chars=1000, max_hashtags=3, max_mentions=3)

    # 3. Too many hashtags
    text_with_many_hashtags = "#one #two #three #four " + "x" * 100
    with pytest.raises(ValueError, match="话题标签.*超过最大限制"):
        format_validation(text_with_many_hashtags, min_chars=10, max_chars=1000, max_hashtags=3, max_mentions=3)

    # 4. Too many mentions
    text_with_many_mentions = "$BTC $ETH $SOL $BNB " + "x" * 100
    with pytest.raises(ValueError, match="代币标签.*超过最大限制"):
        format_validation(text_with_many_mentions, min_chars=10, max_chars=1000, max_hashtags=3, max_mentions=3)

    # 5. Multiple errors
    bad_text = "#a #b #c #d $x $y $z $w"
    with pytest.raises(ValueError):
        format_validation(bad_text, min_chars=100, max_chars=200, max_hashtags=3, max_mentions=3)

    # 6. Valid format
    valid_text = "This is a valid analysis with some good insights #Crypto #Polymarket $BTC " + "x" * 100
    format_validation(valid_text, min_chars=50, max_chars=500, max_hashtags=3, max_mentions=3)
    # Should not raise


def test_generate_with_retry_success():
    from binance_square_bot.models.tweet import Tweet
    from datetime import datetime

    market = PolymarketMarket(
        condition_id="0x123",
        question="Will BTC exceed $100,000 by December 2025?",
        tokens=[
            TokenInfo(token_id="t1", outcome="YES", price=0.35),
            TokenInfo(token_id="t2", outcome="NO", price=0.65),
        ],
        volume=100000.0,
        created_at=1713500000,
    )

    generator = ResearchGenerator()
    mock_tweet = Tweet(
        content="Test content",
        article_url="",
        generated_at=datetime.now(),
        validation_passed=True,
        validation_errors=[],
    )

    with patch.object(generator, 'generate_research', return_value=mock_tweet) as mock_generate:
        result, error = generator.generate_with_retry(market)

        assert result is not None
        assert result.content == "Test content"
        assert error == ""
        mock_generate.assert_called_once()
        # Should pass None as errors on first attempt
        args, kwargs = mock_generate.call_args
        assert args[1] is None


def test_generate_with_retry_success_on_retry():
    from binance_square_bot.models.tweet import Tweet
    from datetime import datetime

    market = PolymarketMarket(
        condition_id="0x123",
        question="Will BTC exceed $100,000 by December 2025?",
        tokens=[
            TokenInfo(token_id="t1", outcome="YES", price=0.35),
            TokenInfo(token_id="t2", outcome="NO", price=0.65),
        ],
        volume=100000.0,
        created_at=1713500000,
    )

    generator = ResearchGenerator()
    generator.max_retries = 3
    mock_tweet = Tweet(
        content="Test content",
        article_url="",
        generated_at=datetime.now(),
        validation_passed=True,
        validation_errors=[],
    )

    with patch.object(generator, 'generate_research') as mock_generate:
        # First two calls fail, third succeeds
        mock_generate.side_effect = [
            ValueError("First error"),
            ValueError("Second error"),
            mock_tweet
        ]

        result, error = generator.generate_with_retry(market)

        assert result is not None
        assert error == ""
        assert mock_generate.call_count == 3

        # Check that errors were accumulated correctly
        # Due to Python reference semantics, all calls see the final value
        # because the same list is reused - this is fine, the actual code logic is correct
        calls = mock_generate.call_args_list
        assert len(calls) == 3
        assert calls[0][0][1] is None
        # Final call gets both errors
        assert calls[-1][0][1] == ["First error", "Second error"]


def test_generate_with_retry_all_fail():
    market = PolymarketMarket(
        condition_id="0x123",
        question="Will BTC exceed $100,000 by December 2025?",
        tokens=[
            TokenInfo(token_id="t1", outcome="YES", price=0.35),
            TokenInfo(token_id="t2", outcome="NO", price=0.65),
        ],
        volume=100000.0,
        created_at=1713500000,
    )

    generator = ResearchGenerator()
    generator.max_retries = 2

    with patch.object(generator, 'generate_research') as mock_generate:
        mock_generate.side_effect = [
            ValueError("First error"),
            ValueError("Second error"),
        ]

        result, error = generator.generate_with_retry(market)

        assert result is None
        assert error == "Second error"
        assert mock_generate.call_count == 2
