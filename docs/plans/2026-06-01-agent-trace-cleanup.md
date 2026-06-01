# Agent Trace Cleanup Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make terminal agent traces clearer by explicitly showing the selected skill and avoiding duplicate/user-prompt message spam.

**Architecture:** Keep trace formatting inside `DeepAgentTweetGenerator`. Track printed trace message previews during a single agent stream, skip user/human messages, print selected skill metadata once before streaming, and keep validation count output unchanged.

**Tech Stack:** Python 3.11+, pytest, DeepAgents/LangGraph stream chunks.

---

### Task 1: Add regression test for clean trace output

**Files:**
- Modify: `tests/services/generation/test_deep_agent_generator.py`
- Modify: `src/binance_square_bot/services/generation/deep_agent_generator.py`

**Step 1: Write the failing test**

Add a test near the existing trace tests:

```python
def test_generate_for_account_trace_skips_duplicate_user_prompts_and_prints_skill(
    monkeypatch, capsys, source_item, generator_config
):
    generator_config.agent_trace_enabled = True
    repeated_prompt = "请基于以下结构化内容生成一条币安广场推文。 item_payload: {...}"
    final_message = "清晰输出只打印一次 #BTC $BTC"
    agent = FakeAgent(
        [],
        stream_chunks=[
            {"messages": [{"role": "user", "content": repeated_prompt}]},
            {"messages": [{"role": "user", "content": repeated_prompt}]},
            {"messages": [{"role": "assistant", "content": final_message}]},
            {"messages": [{"role": "assistant", "content": final_message}]},
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
        api_key_mask="mask-1",
        account_index=1,
    )

    output = capsys.readouterr().out
    assert content == final_message
    assert "Skill selected: fn_news" in output
    assert "Skill path: C:/repo/agent_skills/fn_news" in output
    assert repeated_prompt not in output
    assert output.count(final_message) == 1
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/services/generation/test_deep_agent_generator.py::test_generate_for_account_trace_skips_duplicate_user_prompts_and_prints_skill -v`

Expected: FAIL because current trace prints user prompts, duplicates assistant messages, and does not print `Skill selected:`.

**Step 3: Write minimal implementation**

Modify `DeepAgentTweetGenerator._invoke_agent_with_trace`:

- Print skill details immediately after the attempt header:

```python
print(f"↳ Skill selected: {Path(str(skill_path)).name}")
print(f"↳ Skill path: {skill_path}")
```

- Track printed previews:

```python
printed_previews: set[str] = set()
```

- Pass the set into `_print_trace_chunk`:

```python
self._print_trace_chunk(chunk, printed_previews)
```

Modify `_print_trace_chunk` signature:

```python
def _print_trace_chunk(self, chunk: Any, printed_previews: set[str]) -> None:
```

Add a role helper:

```python
@staticmethod
def _message_role(message: Any) -> str | None:
    if isinstance(message, dict):
        role = message.get("role") or message.get("type")
        return str(role).lower() if role else None
    role = getattr(message, "role", None) or getattr(message, "type", None)
    return str(role).lower() if role else None
```

In `_print_trace_chunk`, skip user/human messages and duplicate previews:

```python
role = self._message_role(message)
if role in {"user", "human"}:
    return
content = self._extract_content(message)
if not content:
    return
preview = " ".join(content.split())[:160]
if preview in printed_previews:
    return
printed_previews.add(preview)
print(f"↳ Agent message: {preview}")
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/services/generation/test_deep_agent_generator.py::test_generate_for_account_trace_skips_duplicate_user_prompts_and_prints_skill -v`

Expected: PASS.

---

### Task 2: Verify trace regression suite

**Files:**
- Test only.

**Step 1: Run generation tests**

Run: `pytest tests/services/generation/test_deep_agent_generator.py -v`

Expected: PASS.

**Step 2: Run full test suite**

Run: `pytest tests/ -v`

Expected: PASS.
