"""
@file test_generator.py
@description 推文格式校验功能测试
@design-doc docs/06-ai-design/agent-flow/tweet-generation-flow.md
@task-id BE-13
@created-by fullstack-dev-workflow
"""

from typing import List


def validate_text(
    text: str,
    min_chars: int = 101,
    max_chars: int = 799,
    max_hashtags: int = 2,
    max_mentions: int = 2,
) -> List[str]:
    """格式校验，返回错误列表"""
    errors: List[str] = []

    # 检查字符数
    length = len(text)
    if length < min_chars:
        errors.append(f"字符数 {length} 小于最小要求 {min_chars}")
    if length > max_chars:
        errors.append(f"字符数 {length} 大于最大要求 {max_chars}")

    # 检查话题标签数量
    hashtag_count = text.count("#")
    if hashtag_count > max_hashtags:
        errors.append(f"话题标签 #{hashtag_count} 个超过最大限制 {max_hashtags}")

    # 检查代币标签数量
    mention_count = text.count("$")
    if mention_count > max_mentions:
        errors.append(f"代币标签 ${mention_count} 个超过最大限制 {max_mentions}")

    return errors


def test_valid_tweet():
    """测试合法推文"""
    text = "比特币价格继续上涨，市场情绪非常乐观。最近美联储加息预期降温，资金开始重新流入加密货币市场，比特币站稳在六万美元上方，长期来看比特币仍然是加密货币市场的领导者，未来仍然值得继续期待，很多机构投资者都在开始加仓。#BTC $BTC"
    errors = validate_text(text)
    assert len(errors) == 0


def test_too_short():
    """测试太短"""
    text = "Short text"
    errors = validate_text(text)
    assert any("小于最小要求" in error for error in errors)


def test_too_long():
    """测试太长"""
    text = "x" * 1000
    errors = validate_text(text)
    assert any("大于最大要求" in error for error in errors)


def test_too_many_hashtags():
    """测试话题标签太多"""
    text = "Bitcoin is going up recently, the market sentiment is very bullish, many institutions are starting to accumulate BTC, and the overall trend looks very good for the next quarter. #BTC #Crypto #Market " + "$BTC"
    errors = validate_text(text)
    assert any("话题标签" in error for error in errors)
    assert len(errors) == 1


def test_too_many_mentions():
    """测试代币标签太多"""
    text = "Multiple altcoins are showing strength recently, many of them have broken key resistance levels and the market trend looks very bullish for the coming weeks. #BTC $BTC $ETH $SOL"
    errors = validate_text(text)
    assert any("代币标签" in error for error in errors)
    assert len(errors) == 1


def test_multiple_errors():
    """测试多个错误"""
    text = "Short #one #two #three $one $two $three"
    errors = validate_text(text)
    # 太短(1) + 3个hashtags(1) + 3个mentions(1) = 3个错误
    assert len(errors) == 3
