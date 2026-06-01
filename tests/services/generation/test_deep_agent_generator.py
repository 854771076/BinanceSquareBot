from types import SimpleNamespace

import pytest

from binance_square_bot.services.generation import DeepAgentTweetGenerator, TweetSourceItem


class FakeAgent:
    def __init__(self, results):
        self.results = list(results)
        self.invocations = []

    def invoke(self, payload):
        self.invocations.append(payload)
        return self.results.pop(0)


@pytest.fixture
def source_item():
    return TweetSourceItem(
        source_name="FnSource",
        content_type="news",
        identifier="https://example.com/news/1",
        title="Bitcoin ETF inflows accelerate",
        summary="Spot Bitcoin ETFs reported another day of strong net inflows.",
        url="https://example.com/news/1",
        metadata={"symbols": ["BTC"]},
    )


@pytest.fixture
def generator_config():
    return SimpleNamespace(
        llm_model="test-model",
        max_retries=3,
        min_chars=10,
        max_chars=120,
        max_hashtags=2,
        max_mentions=2,
    )


def test_generate_for_account_invokes_deep_agent_with_selected_skill_and_returns_valid_content(
    monkeypatch, source_item, generator_config
):
    agent = FakeAgent([{"content": "BTC ETF资金继续流入，市场情绪保持升温 #Bitcoin $BTC"}])
    factory_calls = []

    def fake_factory(**kwargs):
        factory_calls.append(kwargs)
        return agent

    monkeypatch.setattr(
        "binance_square_bot.services.generation.deep_agent_generator.get_config",
        lambda: generator_config,
    )
    monkeypatch.setattr(
        "binance_square_bot.services.generation.deep_agent_generator.select_skill_path",
        lambda item: "C:/repo/agent_skills/fn_news",
    )

    generator = DeepAgentTweetGenerator(agent_factory=fake_factory)

    content = generator.generate_for_account(
        source_item,
        api_key_mask="abcd...wxyz",
        account_index=2,
        api_key="FULL_SECRET_API_KEY",
    )

    assert content == "BTC ETF资金继续流入，市场情绪保持升温 #Bitcoin $BTC"
    assert len(factory_calls) == 1
    assert factory_calls[0]["model"] == "test-model"
    assert isinstance(factory_calls[0]["system_prompt"], str)
    assert "Binance Square" in factory_calls[0]["system_prompt"]
    assert factory_calls[0]["tools"] == []
    assert factory_calls[0]["skills"] == ["C:/repo/agent_skills/fn_news"]
    task = agent.invocations[0]["messages"]
    assert "Bitcoin ETF inflows accelerate" in task
    assert "abcd...wxyz" in task
    assert "account_index" in task
    assert "2" in task
    assert "variation" in task


def test_generate_for_account_retries_with_validation_errors(monkeypatch, source_item, generator_config):
    agent = FakeAgent(
        [
            {"messages": [{"content": "short"}]},
            {"messages": [SimpleNamespace(content="第二次生成满足长度要求，并保留清晰观点 #BTC $BTC")]},
        ]
    )

    monkeypatch.setattr(
        "binance_square_bot.services.generation.deep_agent_generator.get_config",
        lambda: generator_config,
    )
    monkeypatch.setattr(
        "binance_square_bot.services.generation.deep_agent_generator.select_skill_path",
        lambda item: "C:/repo/agent_skills/fn_news",
    )

    generator = DeepAgentTweetGenerator(agent_factory=lambda **kwargs: agent)

    content = generator.generate_for_account(
        source_item,
        api_key_mask="mask-1",
        account_index=1,
    )

    assert content == "第二次生成满足长度要求，并保留清晰观点 #BTC $BTC"
    assert len(agent.invocations) == 2
    retry_task = agent.invocations[1]["messages"]
    assert "上次生成不符合格式要求" in retry_task
    assert "字符数必须在 10-120 之间" in retry_task


def test_generate_for_account_raises_after_all_validation_attempts(
    monkeypatch, source_item, generator_config
):
    generator_config.max_retries = 2
    agent = FakeAgent(["short", {"content": "still"}])

    monkeypatch.setattr(
        "binance_square_bot.services.generation.deep_agent_generator.get_config",
        lambda: generator_config,
    )
    monkeypatch.setattr(
        "binance_square_bot.services.generation.deep_agent_generator.select_skill_path",
        lambda item: "C:/repo/agent_skills/fn_news",
    )

    generator = DeepAgentTweetGenerator(agent_factory=lambda **kwargs: agent)

    with pytest.raises(ValueError, match="DeepAgents generation failed"):
        generator.generate_for_account(
            source_item,
            api_key_mask="mask-2",
            account_index=3,
        )

    assert len(agent.invocations) == 2


def test_generate_for_account_never_includes_full_api_key(monkeypatch, source_item, generator_config):
    full_api_key = "binance_live_full_secret_value"
    agent = FakeAgent([SimpleNamespace(content="安全地为不同账号生成不同角度的内容 #Crypto $BTC")])
    factory_calls = []

    def fake_factory(**kwargs):
        factory_calls.append(kwargs)
        return agent

    monkeypatch.setattr(
        "binance_square_bot.services.generation.deep_agent_generator.get_config",
        lambda: generator_config,
    )
    monkeypatch.setattr(
        "binance_square_bot.services.generation.deep_agent_generator.select_skill_path",
        lambda item: "C:/repo/agent_skills/fn_news",
    )

    generator = DeepAgentTweetGenerator(agent_factory=fake_factory)

    generator.generate_for_account(
        source_item,
        api_key_mask="bina...alue",
        account_index=4,
        api_key=full_api_key,
    )

    serialized_factory_calls = repr(factory_calls)
    serialized_invocations = repr(agent.invocations)
    assert full_api_key not in serialized_factory_calls
    assert full_api_key not in serialized_invocations
    assert "bina...alue" in serialized_invocations
