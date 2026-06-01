# Agent Trace and Generation Limits Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Reduce DeepAgents validation failures from excessive token tags and add an opt-in terminal trace for agent generation attempts.

**Architecture:** Keep `DeepAgentTweetGenerator` as the generation boundary. Make generation constraints explicit in the per-attempt task, then add an `AGENT_TRACE_ENABLED` config flag that switches generation from `agent.invoke()` to `agent.stream(..., stream_mode="values")` and prints concise terminal trace events without exposing full API keys.

**Tech Stack:** Python 3.11+, pytest, pydantic-settings, DeepAgents/LangGraph streaming.

---

### Task 1: Make generation limits explicit in prompts

**Files:**
- Modify: `tests/services/generation/test_deep_agent_generator.py`
- Modify: `src/binance_square_bot/services/generation/deep_agent_generator.py`

**Step 1: Write the failing test**

In `tests/services/generation/test_deep_agent_generator.py`, extend `test_generate_invokes_deep_agent_with_skill_and_returns_valid_content` to assert the generated task includes exact limits:

```python
assert "字符数范围: 10-120" in task
assert "# 话题标签最多 2 个" in task
assert "$ 代币标签最多 2 个" in task
assert "最终输出中 `$` 符号数量不得超过 2" in task
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/services/generation/test_deep_agent_generator.py::test_generate_invokes_deep_agent_with_skill_and_returns_valid_content -v`

Expected: FAIL because `_build_task` does not include concrete config limits yet.

**Step 3: Write minimal implementation**

Modify `DeepAgentTweetGenerator.generate_for_account` to pass `config` into `_build_task`.

Modify `_build_task` signature:

```python
def _build_task(
    self,
    item: TweetSourceItem,
    api_key_mask: str,
    account_index: int,
    attempt: int,
    validation_error: str | None,
    config: Any,
) -> str:
```

Add explicit rules to `parts` after account fields:

```python
(
    "format_limits: "
    f"字符数范围: {config.min_chars}-{config.max_chars}；"
    f"# 话题标签最多 {config.max_hashtags} 个；"
    f"$ 代币标签最多 {config.max_mentions} 个；"
    f"最终输出中 `$` 符号数量不得超过 {config.max_mentions}。"
),
"如果没有明确必要的代币标签，宁可少用或不用；不要为了覆盖多个项目而堆叠 `$TOKEN`。",
```

When `validation_error` exists, append:

```python
"请修复上次错误，优先减少标签数量，不要新增额外 `$` 或 `#` 标签。"
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/services/generation/test_deep_agent_generator.py::test_generate_invokes_deep_agent_with_skill_and_returns_valid_content -v`

Expected: PASS.

---

### Task 2: Add opt-in terminal trace config and streaming path

**Files:**
- Modify: `src/binance_square_bot/config.py`
- Modify: `tests/services/generation/test_deep_agent_generator.py`
- Modify: `src/binance_square_bot/services/generation/deep_agent_generator.py`

**Step 1: Write failing tests**

Add stream support to `FakeAgent`:

```python
class FakeAgent:
    def __init__(self, results, stream_chunks=None):
        self.results = list(results)
        self.stream_chunks = list(stream_chunks or [])
        self.invocations = []
        self.streams = []

    def invoke(self, payload):
        self.invocations.append(payload)
        return self.results.pop(0)

    def stream(self, payload, stream_mode=None):
        self.streams.append({"payload": payload, "stream_mode": stream_mode})
        yield from self.stream_chunks
```

Add `agent_trace_enabled=False` to the `generator_config` fixture.

Add a test:

```python
def test_generate_for_account_streams_and_prints_trace_when_enabled(
    monkeypatch, capsys, source_item, generator_config
):
    generator_config.agent_trace_enabled = True
    agent = FakeAgent(
        [],
        stream_chunks=[
            {"messages": [{"content": "计划：先读取技能，再生成草稿"}]},
            {"messages": [{"content": "合规内容聚焦ETF流入，不堆叠标签 #BTC $BTC"}]},
        ],
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
        api_key_mask="b335d90...7c24",
        account_index=1,
        api_key="FULL_SECRET_API_KEY",
    )

    output = capsys.readouterr().out
    assert content == "合规内容聚焦ETF流入，不堆叠标签 #BTC $BTC"
    assert agent.invocations == []
    assert agent.streams[0]["stream_mode"] == "values"
    assert "Agent attempt 1/3" in output
    assert "FnSource" in output
    assert "fn_news" in output
    assert "b335d90...7c24" in output
    assert "Validation passed" in output
    assert "FULL_SECRET_API_KEY" not in output
```

Add another test for failed validation trace:

```python
def test_generate_for_account_trace_prints_validation_failure_counts(
    monkeypatch, capsys, source_item, generator_config
):
    generator_config.agent_trace_enabled = True
    generator_config.max_retries = 1
    agent = FakeAgent(
        [],
        stream_chunks=[
            {"messages": [{"content": "标签过多 #BTC $BTC $ETH $BNB"}]},
        ],
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

    with pytest.raises(ValueError, match="代币标签不能超过 2 个"):
        generator.generate_for_account(
            source_item,
            api_key_mask="mask-2",
            account_index=3,
        )

    output = capsys.readouterr().out
    assert "Validation failed" in output
    assert "#=1" in output
    assert "$=3" in output
    assert "代币标签不能超过 2 个" in output
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/services/generation/test_deep_agent_generator.py::test_generate_for_account_streams_and_prints_trace_when_enabled tests/services/generation/test_deep_agent_generator.py::test_generate_for_account_trace_prints_validation_failure_counts -v`

Expected: FAIL because config and streaming trace do not exist yet.

**Step 3: Write minimal implementation**

In `src/binance_square_bot/config.py`, add:

```python
agent_trace_enabled: bool = False
```

In `DeepAgentTweetGenerator.generate_for_account`:

- Save `skill_path = select_skill_path(item)` before agent creation or make `_create_agent` return both. Prefer passing `skill_path` into `_create_agent` to avoid double selection.
- If `config.agent_trace_enabled` is true, call a helper `_invoke_with_trace(...)`; otherwise keep existing `agent.invoke(...)`.

Add helpers:

```python
def _invoke_agent(self, agent: Any, task: str, config: Any, *, item: TweetSourceItem, api_key_mask: str, account_index: int, attempt: int, skill_path: Any) -> str:
    payload = {"messages": [{"role": "user", "content": task}]}
    if not getattr(config, "agent_trace_enabled", False):
        return self._extract_content(agent.invoke(payload))
    return self._invoke_agent_with_trace(
        agent,
        payload,
        item=item,
        api_key_mask=api_key_mask,
        account_index=account_index,
        attempt=attempt,
        max_retries=config.max_retries,
        skill_path=skill_path,
    )
```

```python
def _invoke_agent_with_trace(...):
    print(
        "🧠 Agent attempt "
        f"{attempt + 1}/{max_retries} "
        f"source={item.source_name} content_type={item.content_type} "
        f"item={item.identifier} account={api_key_mask} skill={Path(str(skill_path)).name}"
    )
    last_chunk = None
    for chunk in agent.stream(payload, stream_mode="values"):
        last_chunk = chunk
        self._print_trace_chunk(chunk)
    content = self._extract_content(last_chunk)
    print(f"↳ Raw output counts: #={content.count('#')} $={content.count('$')}")
    return content
```

Add `_print_trace_chunk` that extracts the newest message from a chunk and prints a sanitized one-line preview (for example first 160 chars), without full API keys because only masked key is in payload.

After validation success/failure in `generate_for_account`, print:

```python
if getattr(config, "agent_trace_enabled", False):
    print("↳ Validation passed")
```

and in the exception block:

```python
if getattr(config, "agent_trace_enabled", False):
    print(f"↳ Validation failed: {validation_error} (#={content.count('#')} $={content.count('$')})")
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/services/generation/test_deep_agent_generator.py::test_generate_for_account_streams_and_prints_trace_when_enabled tests/services/generation/test_deep_agent_generator.py::test_generate_for_account_trace_prints_validation_failure_counts -v`

Expected: PASS.

---

### Task 3: Regression verification

**Files:**
- Test only.

**Step 1: Run generation tests**

Run: `pytest tests/services/generation/test_deep_agent_generator.py tests/services/generation/test_validator.py -v`

Expected: PASS.

**Step 2: Run full test suite**

Run: `pytest tests/ -v`

Expected: PASS.

**Step 3: Review diff**

Run: `git diff -- src/binance_square_bot/config.py src/binance_square_bot/services/generation/deep_agent_generator.py tests/services/generation/test_deep_agent_generator.py`

Expected: Diff only includes explicit limit prompting, trace config, trace helpers, and tests.
