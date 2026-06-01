import pytest

from binance_square_bot.services.source import followin_source as followin_module
from binance_square_bot.services.source.followin_source import (
    FollowinSource,
    FollowinTopic,
)


def test_followin_topic_model():
    """Test FollowinTopic model validation."""
    topic = FollowinTopic(
        id=123,
        title="Trending topic",
        summary="A useful summary",
        url="https://followin.io/topic/123",
    )

    assert topic.id == 123
    assert topic.title == "Trending topic"
    assert topic.summary == "A useful summary"


def test_followin_source_constructs_without_llm_api_key(monkeypatch):
    """FollowinSource construction must not initialize the legacy source-level LLM."""
    monkeypatch.delenv("LLM_API_KEY", raising=False)

    def fail_if_called(*args, **kwargs):
        raise AssertionError("FollowinSource constructor should not create ChatOpenAI")

    monkeypatch.setattr(followin_module, "ChatOpenAI", fail_if_called, raising=False)

    source = FollowinSource()

    assert source.session is not None
    assert source.processed_ids == set()
    assert not hasattr(source, "llm")


def test_followin_generate_is_deprecated_stub(monkeypatch):
    """Legacy Followin generation should point callers to DeepAgents."""

    class FailIfInvokedLLM:
        def invoke(self, *args, **kwargs):
            raise AssertionError("Deprecated Followin generation should not call LLM")

    monkeypatch.setattr(
        followin_module,
        "ChatOpenAI",
        lambda *args, **kwargs: FailIfInvokedLLM(),
        raising=False,
    )
    source = FollowinSource()
    topic = FollowinTopic(
        id=123,
        title="Trending topic",
        summary="A useful summary",
        url="https://followin.io/topic/123",
    )

    with pytest.raises(
        RuntimeError,
        match="DeepAgentTweetGenerator.*TweetSourceItem",
    ):
        source.generate([topic])
