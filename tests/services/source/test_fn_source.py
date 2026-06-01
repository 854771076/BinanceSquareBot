import pytest

from binance_square_bot.services.source import fn_source as fn_module
from binance_square_bot.services.source.fn_source import (
    AirdropEvent,
    Article,
    CalendarEvent,
    FnSource,
    FundraisingEvent,
)


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


def test_fn_source_constructs_without_llm_api_key(monkeypatch):
    """FnSource construction must not initialize the legacy source-level LLM."""
    monkeypatch.delenv("LLM_API_KEY", raising=False)

    def fail_if_called(*args, **kwargs):
        raise AssertionError("FnSource constructor should not create ChatOpenAI")

    monkeypatch.setattr(fn_module, "ChatOpenAI", fail_if_called, raising=False)

    source = FnSource()

    assert source.session is not None
    assert not hasattr(source, "llm")


def test_fn_generation_methods_are_deprecated_stubs(monkeypatch):
    """Legacy Fn generation methods should point callers to DeepAgents."""

    class FailIfInvokedLLM:
        def invoke(self, *args, **kwargs):
            raise AssertionError("Deprecated Fn generation should not call LLM")

    monkeypatch.setattr(
        fn_module,
        "ChatOpenAI",
        lambda *args, **kwargs: FailIfInvokedLLM(),
        raising=False,
    )
    source = FnSource()

    cases = [
        (
            source.generate,
            [Article(title="Title", url="https://example.com", content="Summary")],
        ),
        (
            source.generate_calendar,
            [
                CalendarEvent(
                    title="Event",
                    url="https://example.com/event",
                    description="Description",
                )
            ],
        ),
        (
            source.generate_airdrops,
            [
                AirdropEvent(
                    id=1,
                    title="Airdrop",
                    url="https://example.com/airdrop",
                    brief="Brief",
                )
            ],
        ),
        (
            source.generate_fundraising,
            [
                FundraisingEvent(
                    id=1,
                    project_name="Project",
                    description="Description",
                    investors=[],
                    url="https://example.com/fundraising",
                )
            ],
        ),
    ]

    for method, items in cases:
        with pytest.raises(
            RuntimeError,
            match="DeepAgentTweetGenerator.*TweetSourceItem",
        ):
            method(items)
