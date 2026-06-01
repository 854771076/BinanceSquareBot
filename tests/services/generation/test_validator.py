import pytest

from binance_square_bot.services.generation.validator import TweetContentValidator


def test_valid_content_passes_validation():
    validator = TweetContentValidator(
        min_chars=10,
        max_chars=80,
        max_hashtags=2,
        max_mentions=1,
    )

    validator.validate("BTC 市场情绪回暖，关注链上资金流向 #BTC $BTC")


def test_rejects_empty_output():
    validator = TweetContentValidator(
        min_chars=5,
        max_chars=80,
        max_hashtags=2,
        max_mentions=1,
    )

    with pytest.raises(ValueError) as exc_info:
        validator.validate("   ")

    assert "空" in str(exc_info.value)


def test_rejects_content_shorter_than_min_chars_with_character_count_error():
    validator = TweetContentValidator(
        min_chars=10,
        max_chars=80,
        max_hashtags=2,
        max_mentions=1,
    )

    with pytest.raises(ValueError) as exc_info:
        validator.validate("太短")

    assert "字符数" in str(exc_info.value)


def test_rejects_content_longer_than_max_chars_with_character_count_error():
    validator = TweetContentValidator(
        min_chars=5,
        max_chars=10,
        max_hashtags=2,
        max_mentions=1,
    )

    with pytest.raises(ValueError) as exc_info:
        validator.validate("这是一段明显超过最大限制的推文")

    assert "字符数" in str(exc_info.value)


def test_rejects_too_many_hashtags_with_hashtag_error():
    validator = TweetContentValidator(
        min_chars=5,
        max_chars=80,
        max_hashtags=1,
        max_mentions=3,
    )

    with pytest.raises(ValueError) as exc_info:
        validator.validate("市场持续关注热点 #BTC #ETH $BTC")

    assert "话题标签" in str(exc_info.value)


def test_rejects_too_many_token_mentions_with_token_tag_error():
    validator = TweetContentValidator(
        min_chars=5,
        max_chars=80,
        max_hashtags=3,
        max_mentions=1,
    )

    with pytest.raises(ValueError) as exc_info:
        validator.validate("资金轮动继续扩大 #Crypto $BTC $ETH")

    assert "代币标签" in str(exc_info.value)


def test_rejects_markdown_code_fences_with_code_block_error():
    validator = TweetContentValidator(
        min_chars=5,
        max_chars=120,
        max_hashtags=3,
        max_mentions=1,
    )

    with pytest.raises(ValueError) as exc_info:
        validator.validate("```\nBTC 市场情绪回暖 #BTC\n```")

    assert "代码块" in str(exc_info.value)


@pytest.mark.parametrize(
    "wrapper",
    ["以下是推文", "推文如下", "这是推文", "当然", "好的"],
)
def test_rejects_explanatory_wrappers_with_wrapper_error(wrapper: str):
    validator = TweetContentValidator(
        min_chars=5,
        max_chars=120,
        max_hashtags=3,
        max_mentions=1,
    )

    with pytest.raises(ValueError) as exc_info:
        validator.validate(f"{wrapper}：BTC 市场情绪回暖 #BTC")

    assert "包装说明" in str(exc_info.value)
