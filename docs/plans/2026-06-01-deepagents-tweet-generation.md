# DeepAgents Tweet Generation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace direct source-level LLM tweet generation with DeepAgents skills and generate a fresh account-specific tweet for every selected content item and every available Binance account.

**Architecture:** Sources fetch and normalize content into `TweetSourceItem` objects. A shared DeepAgents generator selects a repository skill, invokes DeepAgents, validates the result, and retries with validation feedback. Publishing loops over `(item, api_key)` pairs, generating immediately before publish so each account gets distinct copy.

**Tech Stack:** Python 3.11, Typer, Pydantic v2, SQLAlchemy/SQLite, DeepAgents, LangChain/OpenAI-compatible model configuration, pytest, Ruff, mypy.

---

## Notes before implementation

- Use TDD. Each task starts with a failing test, then minimal implementation.
- Do not send full Binance API keys to DeepAgents. Use `mask_api_key()` or an account ordinal only.
- Keep `--dry-run` safe: generate text, print masked keys, do not call `publish()` or increment counters.
- `total_per_run` limits content items, not account-level generated tweets.
- Existing tests that expect one tweet assigned to one key must be updated to the new semantics.
- DeepAgents docs show `from deepagents import create_deep_agent` and `agent.invoke({"messages": "..."})`; use a small adapter so tests can mock the factory without real LLM calls.

---

### Task 1: Add DeepAgents dependency

**Files:**
- Modify: `pyproject.toml`

**Step 1: Add dependency**

In `[project].dependencies`, add:

```toml
  "deepagents>=0.0.1",
```

Do not remove LangChain packages yet; DeepAgents may rely on LangChain-compatible model plumbing, and some legacy code remains during migration.

**Step 2: Validate metadata parses**

Run: `python -m pip install -e .`

Expected: package installs successfully. If dependency resolution fails because the version is wrong, check the installed package name/version and use the currently published `deepagents` version.

**Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "chore: add deepagents dependency"
```

---

### Task 2: Create normalized tweet content model

**Files:**
- Create: `src/binance_square_bot/services/generation/__init__.py`
- Create: `src/binance_square_bot/services/generation/models.py`
- Test: `tests/services/generation/test_models.py`

**Step 1: Write failing tests**

Create `tests/services/generation/test_models.py`:

```python
from binance_square_bot.services.generation.models import TweetSourceItem


def test_tweet_source_item_requires_stable_identity():
    item = TweetSourceItem(
        source_name="FnSource",
        content_type="news",
        identifier="https://example.com/news/1",
        title="Title",
        summary="Summary",
        url="https://example.com/news/1",
        metadata={"foo": "bar"},
    )

    assert item.source_name == "FnSource"
    assert item.content_type == "news"
    assert item.identifier == "https://example.com/news/1"
    assert item.metadata == {"foo": "bar"}


def test_tweet_source_item_to_prompt_payload_excludes_none_url():
    item = TweetSourceItem(
        source_name="FollowinSource",
        content_type="topics",
        identifier="123",
        title="Topic",
        summary="Summary",
    )

    payload = item.to_prompt_payload()

    assert payload["source_name"] == "FollowinSource"
    assert payload["content_type"] == "topics"
    assert payload["identifier"] == "123"
    assert "url" not in payload
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/services/generation/test_models.py -v`

Expected: FAIL because `binance_square_bot.services.generation` does not exist.

**Step 3: Implement model**

Create `src/binance_square_bot/services/generation/__init__.py`:

```python
"""Tweet generation services."""

from .models import TweetSourceItem

__all__ = ["TweetSourceItem"]
```

Create `src/binance_square_bot/services/generation/models.py`:

```python
from typing import Any

from pydantic import BaseModel, Field


class TweetSourceItem(BaseModel):
    """Normalized source content ready for tweet generation."""

    source_name: str
    content_type: str
    identifier: str
    title: str
    summary: str
    url: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_prompt_payload(self) -> dict[str, Any]:
        payload = self.model_dump()
        if payload.get("url") is None:
            payload.pop("url", None)
        if not payload.get("metadata"):
            payload.pop("metadata", None)
        return payload
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/services/generation/test_models.py -v`

Expected: PASS.

**Step 5: Commit**

```bash
git add src/binance_square_bot/services/generation tests/services/generation/test_models.py
git commit -m "feat: add normalized tweet source item"
```

---

### Task 3: Add source-to-item mappers

**Files:**
- Create: `src/binance_square_bot/services/generation/mappers.py`
- Test: `tests/services/generation/test_mappers.py`

Follow the approved design in `docs/plans/2026-06-01-deepagents-tweet-generation-design.md`. Add mapper tests for Fn article/calendar/airdrop/fundraising, Followin topic/token, and Polymarket market. Implement only the mappers needed by those tests.

---

### Task 4: Add shared tweet validation

**Files:**
- Create: `src/binance_square_bot/services/generation/validator.py`
- Test: `tests/services/generation/test_validator.py`

Implement `TweetContentValidator` with min/max chars, hashtag count, token mention count, empty-output checks, and wrapper/code-fence rejection.

---

### Task 5: Add skill selector and repository skill files

**Files:**
- Create: `src/binance_square_bot/services/generation/skills.py`
- Create: `agent_skills/*/SKILL.md`
- Test: `tests/services/generation/test_skills.py`

Add skill selection for Fn news/calendar/airdrop/fundraising, Followin topics/token, and Polymarket research. Create concise Markdown skill files with writing rules copied from existing prompt intent.

---

### Task 6: Implement DeepAgentTweetGenerator

**Files:**
- Create: `src/binance_square_bot/services/generation/deep_agent_generator.py`
- Modify: `src/binance_square_bot/services/generation/__init__.py`
- Test: `tests/services/generation/test_deep_agent_generator.py`

Implement a factory-wrapped DeepAgents generator with validation retry and safe masked-key context. Tests must mock the agent factory; no real LLM calls.

---

### Task 7: Add account-level item publisher

**Files:**
- Create: `src/binance_square_bot/services/account_item_publisher.py`
- Test: `tests/services/test_account_item_publisher.py`

Implement publisher that loops over each item and each available API key, generates per account, publishes unless dry-run, increments per-key counts after success, and marks content published only when at least one account succeeds.

---

### Task 8: Migrate Fn CLI workflows to item publishing

**Files:**
- Modify: `src/binance_square_bot/services/cli/fn_cli.py`
- Test: `tests/services/cli/test_fn_cli.py`

Replace source-level generation calls with mapper output and `AccountItemPublisher`. Preserve daily execution checks and current storage content types.

---

### Task 9: Migrate Followin CLI workflows to item publishing

**Files:**
- Modify: `src/binance_square_bot/services/cli/followin_cli.py`
- Test: `tests/services/cli/test_followin_cli.py`

Replace `source.generate()` with Followin item mapping and `AccountItemPublisher`. Preserve `topics`, `io_flow`, and `discussion` storage content types.

---

### Task 10: Migrate Polymarket CLI workflow to item publishing

**Files:**
- Modify: `src/binance_square_bot/services/cli/polymarket_cli.py`
- Test: `tests/services/cli/test_polymarket_cli.py`

Move candidate filtering from `PolymarketSource.generate()` into CLI workflow, map candidates to items, and publish through account item publisher.

---

### Task 11: Update parallel orchestrator semantics

**Files:**
- Modify: `src/binance_square_bot/services/concurrent_executor.py`
- Test: `tests/services/test_concurrent_executor.py`

Update parallel publishing to operate on content items, not pre-generated tweets. Deduplicate at item level, apply `total_per_run` to items, and delegate account-level generation/publishing to `AccountItemPublisher`.

---

### Task 12: Return item lists from CLI services for parallel workflow

**Files:**
- Modify: `src/binance_square_bot/services/cli/fn_cli.py`
- Modify: `src/binance_square_bot/services/cli/followin_cli.py`
- Modify: `src/binance_square_bot/services/cli/polymarket_cli.py`
- Modify tests under `tests/services/cli/`

Ensure CLI service results include `items_generated` with `TweetSourceItem` objects and `items_fetched` counts. Avoid using `tweets_generated` for source-stage output.

---

### Task 13: Update CLI and docs references

**Files:**
- Modify: `CLAUDE.md`
- Modify: `README.md`
- Modify: `.env_example` only if new env vars are introduced

Document that DeepAgents skills generate per-account tweets and `total_per_run` limits content items.

---

### Task 14: Remove obsolete direct generation paths where safe

**Files:**
- Modify: `src/binance_square_bot/services/source/fn_source.py`
- Modify: `src/binance_square_bot/services/source/followin_source.py`
- Modify: `src/binance_square_bot/services/source/polymarket_source.py`
- Modify source tests if needed

Remove direct `ChatOpenAI.invoke()` source-level generation if no remaining caller needs it. Compatibility stubs are acceptable if tests or external API shape require them.

---

### Task 15: Full verification

Run:

```bash
python -m pytest tests/ -v
ruff check src/ tests/
mypy src/
binance-square-bot parallel --dry-run --workers 2 --total-per-run 1
```

Expected: tests, lint, and type check pass. Dry-run generates per-account content with masked keys and does not publish.
