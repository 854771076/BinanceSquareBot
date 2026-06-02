# Skill Verification Logging Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make agent trace logs show reliable evidence that a selected skill was configured and passed into DeepAgents, while clearly reporting whether runtime stream evidence is exposed.

**Architecture:** Keep logging inside `DeepAgentTweetGenerator`. At trace time, print skill file metadata and the exact skills list passed to the agent factory. During streaming, inspect messages/chunks for tool calls or skill-related metadata; if none is observed, print that no explicit runtime skill event was exposed by the stream.

**Tech Stack:** Python 3.11+, pytest, DeepAgents/LangGraph stream chunks.

---

### Task 1: Add failing tests for skill configuration evidence

**Files:**
- Modify: `tests/services/generation/test_deep_agent_generator.py`
- Modify: `src/binance_square_bot/services/generation/deep_agent_generator.py`

**Step 1: Write failing test**

Add a test near existing trace tests:

```python
def test_generate_for_account_trace_prints_skill_configuration_evidence(
    monkeypatch, capsys, tmp_path, source_item, generator_config
):
    generator_config.agent_trace_enabled = True
    skill_dir = tmp_path / "fn_news"
    skill_dir.mkdir()
    skill_file = skill_dir / "SKILL.md"
    skill_file.write_text("# Skill\n\nUse a natural hook.", encoding="utf-8")
    agent = FakeAgent(
        [],
        stream_chunks=[{"messages": [{"role": "assistant", "content": "合规内容 #BTC $BTC"}]}],
    )

    monkeypatch.setattr(
        "binance_square_bot.services.generation.deep_agent_generator.get_config",
        lambda: generator_config,
    )
    monkeypatch.setattr(
        "binance_square_bot.services.generation.deep_agent_generator.select_skill_path",
        lambda item: skill_dir,
    )

    generator = DeepAgentTweetGenerator(agent_factory=lambda **kwargs: agent)

    generator.generate_for_account(
        source_item,
        api_key_mask="mask-1",
        account_index=1,
    )

    output = capsys.readouterr().out
    assert "Skill configured: fn_news" in output
    assert "SKILL.md exists=True" in output
    assert "Skill digest:" in output
    assert "Agent factory skills:" in output
    assert str(skill_dir) in output
    assert "Runtime skill event: not exposed by stream" in output
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/services/generation/test_deep_agent_generator.py::test_generate_for_account_trace_prints_skill_configuration_evidence -v`

Expected: FAIL because current trace only prints `Skill selected` and `Skill path`.

---

### Task 2: Add failing test for runtime tool-call evidence

**Files:**
- Modify: `tests/services/generation/test_deep_agent_generator.py`
- Modify: `src/binance_square_bot/services/generation/deep_agent_generator.py`

**Step 1: Write failing test**

Add a test near existing trace tests:

```python
def test_generate_for_account_trace_prints_tool_call_runtime_evidence(
    monkeypatch, capsys, source_item, generator_config
):
    generator_config.agent_trace_enabled = True
    agent = FakeAgent(
        [],
        stream_chunks=[
            {
                "messages": [
                    {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [{"name": "read_skill", "args": {"skill": "fn_news"}}],
                    }
                ]
            },
            {"messages": [{"role": "assistant", "content": "合规内容 #BTC $BTC"}]},
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

    generator.generate_for_account(
        source_item,
        api_key_mask="mask-1",
        account_index=1,
    )

    output = capsys.readouterr().out
    assert "Tool call: read_skill" in output
    assert "Runtime skill event: observed" in output
    assert "not exposed by stream" not in output
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/services/generation/test_deep_agent_generator.py::test_generate_for_account_trace_prints_tool_call_runtime_evidence -v`

Expected: FAIL because current trace ignores `tool_calls`.

---

### Task 3: Implement skill verification trace logging

**Files:**
- Modify: `src/binance_square_bot/services/generation/deep_agent_generator.py`

**Step 1: Add imports**

Add:

```python
import hashlib
```

**Step 2: Pass factory skills into trace helper**

In `_invoke_agent`, create:

```python
agent_skills = [str(skill_path)]
```

Pass `agent_skills=agent_skills` into `_invoke_agent_with_trace`.

**Step 3: Print skill configuration evidence**

Add helper:

```python
def _print_skill_configuration_trace(self, skill_path: Any, agent_skills: list[str]) -> None:
    path = Path(str(skill_path))
    skill_file = path / "SKILL.md"
    exists = skill_file.is_file()
    digest = "missing"
    size = 0
    if exists:
        data = skill_file.read_bytes()
        size = len(data)
        digest = hashlib.sha256(data).hexdigest()[:12]
    print(f"↳ Skill configured: {path.name}")
    print(f"↳ Skill path: {path}")
    print(f"↳ SKILL.md exists={exists} size={size}")
    print(f"↳ Skill digest: {digest}")
    print(f"↳ Agent factory skills: {agent_skills}")
```

Call it after the attempt header.

**Step 4: Detect runtime evidence**

Change `_print_trace_chunk` to return `bool` meaning runtime evidence observed.

Add helpers:

```python
def _print_tool_calls(self, message: Any) -> bool:
    tool_calls = self._message_tool_calls(message)
    observed = False
    for tool_call in tool_calls:
        name = self._tool_call_name(tool_call)
        if name:
            print(f"↳ Tool call: {name}")
            observed = True
    return observed
```

Support dict and object messages:

```python
@staticmethod
def _message_tool_calls(message: Any) -> list[Any]:
    if isinstance(message, dict):
        calls = message.get("tool_calls") or []
    else:
        calls = getattr(message, "tool_calls", []) or []
    return list(calls) if isinstance(calls, list) else []
```

```python
@staticmethod
def _tool_call_name(tool_call: Any) -> str | None:
    if isinstance(tool_call, dict):
        value = tool_call.get("name")
        return str(value) if value else None
    value = getattr(tool_call, "name", None)
    return str(value) if value else None
```

In `_invoke_agent_with_trace`, aggregate:

```python
runtime_evidence_observed = False
...
runtime_evidence_observed = self._print_trace_chunk(...) or runtime_evidence_observed
...
if runtime_evidence_observed:
    print("↳ Runtime skill event: observed")
else:
    print("↳ Runtime skill event: not exposed by stream")
```

**Step 5: Run failing tests to verify they pass**

Run both new tests:

```powershell
pytest tests/services/generation/test_deep_agent_generator.py::test_generate_for_account_trace_prints_skill_configuration_evidence tests/services/generation/test_deep_agent_generator.py::test_generate_for_account_trace_prints_tool_call_runtime_evidence -v
```

Expected: PASS.

---

### Task 4: Regression verification

**Files:**
- Test only.

**Step 1: Run generator tests**

Run: `pytest tests/services/generation/test_deep_agent_generator.py -v`

Expected: PASS.

**Step 2: Run full test suite when user permits**

Run: `pytest tests/ -v`

Expected: PASS. If the user rejects full test execution, report that focused tests passed and full suite was skipped by user interruption.
