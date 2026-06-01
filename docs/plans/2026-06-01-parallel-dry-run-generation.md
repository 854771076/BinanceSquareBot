# Parallel Dry Run Generation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Ensure `parallel --dry-run` still generates and prints account-specific articles while never publishing or updating runtime state.

**Architecture:** `SourceOrchestrator.run_sources` should collect source items, aggregate them, apply the existing item selection path, and delegate to `SourceParallelPublisher` even when `dry_run=True`. The existing `dry_run` propagation into `SourceParallelPublisher` and `AccountItemPublisher` will keep publishing and state mutation disabled.

**Tech Stack:** Python 3.11+, pytest, unittest.mock, existing Typer service layer.

---

### Task 1: Add dry-run orchestration regression test

**Files:**
- Modify: `tests/services/test_concurrent_executor.py`

**Step 1: Write the failing test**

Add a test near `test_run_sources_dry_run_does_not_increment_collected_workflow_keys`:

```python
def test_run_sources_dry_run_still_delegates_items_to_publisher(self) -> None:
    """Dry-run parallel execution generates/prints via publisher without state increments."""
    item = make_item("fn-news", content_type="news")
    orchestrator = SourceOrchestrator(max_workers=1)
    target = MockTarget()
    storage = Mock()

    service = Mock()
    service.collect_items.return_value = {"items_generated": [item]}
    service_cls = Mock(return_value=service)

    with (
        patch.object(orchestrator, "_get_service_for_source", return_value=service_cls),
        patch(
            "binance_square_bot.services.concurrent_executor.SourceParallelPublisher"
        ) as publisher_cls,
    ):
        publisher_cls.return_value.publish_to_targets.return_value = {
            "generated_success": 1,
            "published_success": 0,
        }
        result = orchestrator.run_sources(
            source_configs=[{"source": type("FnSource", (), {})()}],
            targets=[target],
            api_keys_map={"MockTarget": ["key-1"]},
            storage=storage,
            dry_run=True,
        )

    publisher_cls.return_value.publish_to_targets.assert_called_once()
    assert publisher_cls.return_value.publish_to_targets.call_args.kwargs["tweets"] == [
        item
    ]
    assert publisher_cls.return_value.publish_to_targets.call_args.kwargs["dry_run"] is True
    assert result["publish_results"] == {
        "generated_success": 1,
        "published_success": 0,
    }
    storage.increment_daily_execution.assert_not_called()
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/services/test_concurrent_executor.py::TestSourceOrchestrator::test_run_sources_dry_run_still_delegates_items_to_publisher -v`

Expected: FAIL because `SourceParallelPublisher.publish_to_targets` is not called when `dry_run=True`.

**Step 3: Write minimal implementation**

Modify `src/binance_square_bot/services/concurrent_executor.py` in `SourceOrchestrator.run_sources`:

- Remove the early return block:

```python
if dry_run:
    console.print("[yellow]🏁 Dry run complete - no publishing[/yellow]")
    return total_stats
```

- Optionally update the publishing status message to distinguish dry-run generation from real publishing:

```python
action = "Generating dry-run posts for" if dry_run else "Publishing"
console.print(
    f"[blue]📤 {action} {len(all_items)} items "
    f"to {len(targets)} targets[/blue]"
)
```

Do not change `_increment_collected_source_executions`; it already returns immediately for dry runs.

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/services/test_concurrent_executor.py::TestSourceOrchestrator::test_run_sources_dry_run_still_delegates_items_to_publisher -v`

Expected: PASS.

**Step 5: Run focused regression tests**

Run: `python -m pytest tests/services/test_concurrent_executor.py tests/services/test_account_item_publisher.py -v`

Expected: PASS.
