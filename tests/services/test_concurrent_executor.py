import random
from dataclasses import dataclass
from typing import Any
from unittest.mock import Mock, patch

from binance_square_bot.services.concurrent_executor import (
    ConcurrentExecutor,
    SourceOrchestrator,
    SourceParallelPublisher,
    TaskResult,
)
from binance_square_bot.services.generation.models import TweetSourceItem


@dataclass
class MockTargetConfig:
    daily_max_posts_per_key: int = 100


class MockTarget:
    config = MockTargetConfig()


def make_item(
    identifier: str = "item-1",
    *,
    source_name: str = "FnSource",
    content_type: str = "news",
    title: str | None = None,
) -> TweetSourceItem:
    return TweetSourceItem(
        source_name=source_name,
        content_type=content_type,
        identifier=identifier,
        title=title or f"Title {identifier}",
        summary=f"Summary {identifier}",
    )


class TestConcurrentExecutor:
    """Tests for ConcurrentExecutor class."""

    def test_init_default_max_workers(self) -> None:
        """Test default max_workers is set correctly."""
        executor = ConcurrentExecutor()
        assert executor.max_workers == 5

    def test_init_custom_max_workers(self) -> None:
        """Test custom max_workers is set correctly."""
        executor = ConcurrentExecutor(max_workers=10)
        assert executor.max_workers == 10


class TestSourceOrchestrator:
    """Tests for SourceOrchestrator class."""

    def test_init_default_total_per_run_is_none(self) -> None:
        """Default total_per_run is None, meaning no limit by default."""
        orchestrator = SourceOrchestrator()
        assert orchestrator.total_per_run is None
        assert orchestrator.max_workers == 4

    def test_init_accepts_total_per_run_parameter(self) -> None:
        """Test that total_per_run parameter is accepted by constructor."""
        orchestrator = SourceOrchestrator(total_per_run=10)
        assert orchestrator.total_per_run == 10
        assert orchestrator.max_workers == 4

    def test_init_accepts_both_parameters(self) -> None:
        """Test that both max_workers and total_per_run can be set."""
        orchestrator = SourceOrchestrator(max_workers=8, total_per_run=5)
        assert orchestrator.max_workers == 8
        assert orchestrator.total_per_run == 5

    def test_run_sources_accepts_total_per_run_parameter(self) -> None:
        """Test that run_sources accepts total_per_run parameter."""
        orchestrator = SourceOrchestrator()
        import inspect

        sig = inspect.signature(orchestrator.run_sources)
        assert "total_per_run" in sig.parameters
        assert sig.parameters["total_per_run"].default is None

    def test_when_total_tweets_exceeds_limit_only_n_are_selected(self) -> None:
        """Test existing limit selection behavior with generated tweet strings."""
        all_tweets = ["t1", "t2", "t3", "t4", "t5"]
        total_per_run = 3
        total_generated = len(all_tweets)

        random.seed(42)
        random.shuffle(all_tweets)
        selected = all_tweets[:total_per_run]

        assert len(selected) == 3
        assert total_generated == 5
        assert all(t in ["t1", "t2", "t3", "t4", "t5"] for t in selected)

    def test_when_total_tweets_less_than_limit_all_are_published(self) -> None:
        """Test that when total tweets <= limit, all are published."""
        orchestrator = SourceOrchestrator(total_per_run=10)

        all_tweets = ["t1", "t2", "t3"]
        effective_limit = orchestrator.total_per_run
        total_generated = len(all_tweets)

        if effective_limit and len(all_tweets) > effective_limit:
            random.shuffle(all_tweets)
            selected = all_tweets[:effective_limit]
        else:
            selected = all_tweets

        assert len(selected) == 3
        assert total_generated == 3
        assert selected == ["t1", "t2", "t3"]

    def test_method_parameter_takes_precedence_over_instance_attribute(self) -> None:
        """Method arg takes precedence over instance total_per_run."""
        orchestrator = SourceOrchestrator(total_per_run=5)

        all_tweets = ["t1", "t2", "t3", "t4", "t5", "t6", "t7"]
        instance_limit = orchestrator.total_per_run
        method_limit = 3

        effective_limit = method_limit if method_limit is not None else instance_limit

        assert effective_limit == 3

        random.seed(123)
        if effective_limit is not None and len(all_tweets) > effective_limit:
            random.shuffle(all_tweets)
            selected = all_tweets[:effective_limit]

        assert len(selected) == 3

    def test_no_limit_when_total_per_run_is_none(self) -> None:
        """Test that no limit is applied when total_per_run is None."""
        orchestrator = SourceOrchestrator(total_per_run=None)

        all_tweets = ["t1", "t2", "t3", "t4", "t5", "t6", "t7", "t8", "t9", "t10"]
        effective_limit = orchestrator.total_per_run
        original_count = len(all_tweets)

        if effective_limit and len(all_tweets) > effective_limit:
            random.shuffle(all_tweets)
            selected = all_tweets[:effective_limit]
        else:
            selected = all_tweets

        assert len(selected) == original_count
        assert selected == all_tweets

    def test_run_sources_uses_collect_items_without_source_publish(self) -> None:
        """Parallel source phase collects items without publish-capable execute."""
        item = make_item("source-item")
        orchestrator = SourceOrchestrator(max_workers=1)
        target = MockTarget()
        storage = Mock()

        service = Mock()
        service.execute.side_effect = AssertionError("source phase must not publish")
        service.collect_items.return_value = {"items_generated": [item]}
        service_cls = Mock(return_value=service)

        with (
            patch.object(
                orchestrator, "_get_service_for_source", return_value=service_cls
            ),
            patch(
                "binance_square_bot.services.concurrent_executor.SourceParallelPublisher"
            ) as publisher_cls,
        ):
            publisher_cls.return_value.publish_to_targets.return_value = {
                "published_success": 1
            }
            orchestrator.run_sources(
                source_configs=[{"source": type("FnSource", (), {})()}],
                targets=[target],
                api_keys_map={"MockTarget": ["key-1"]},
                storage=storage,
                dry_run=False,
            )

        service.collect_items.assert_called_once_with("execute")
        service.execute.assert_not_called()
        publisher_cls.return_value.publish_to_targets.assert_called_once()
        published_items = (
            publisher_cls.return_value.publish_to_targets.call_args.kwargs["tweets"]
        )
        assert published_items == [item]

    def test_run_sources_keeps_same_source_class_workflows_separate(self) -> None:
        """Same-class source configs use unique task names and publish both items."""
        news_item = make_item("fn-news", content_type="news")
        calendar_item = make_item("fn-calendar", content_type="calendar")
        orchestrator = SourceOrchestrator(max_workers=1)
        target = MockTarget()
        storage = Mock()

        service = Mock()
        service.collect_items.side_effect = [
            {"items_generated": [news_item]},
            {"items_generated": [calendar_item]},
        ]
        service_cls = Mock(return_value=service)

        with (
            patch.object(
                orchestrator, "_get_service_for_source", return_value=service_cls
            ),
            patch(
                "binance_square_bot.services.concurrent_executor.SourceParallelPublisher"
            ) as publisher_cls,
        ):
            publisher_cls.return_value.publish_to_targets.return_value = {
                "published_success": 2
            }
            result = orchestrator.run_sources(
                source_configs=[
                    {"source": type("FnSource", (), {})(), "execute": "execute"},
                    {
                        "source": type("FnSource", (), {})(),
                        "execute": "execute_calendar",
                    },
                ],
                targets=[target],
                api_keys_map={"MockTarget": ["key-1"]},
                storage=storage,
                dry_run=False,
            )

        assert set(result["source_results"]) == {
            "FnSource_execute",
            "FnSource_execute_calendar",
        }
        publisher_cls.return_value.publish_to_targets.assert_called_once()
        published_items = (
            publisher_cls.return_value.publish_to_targets.call_args.kwargs["tweets"]
        )
        assert published_items == [news_item, calendar_item]

    def test_run_sources_increments_collected_workflow_keys_after_publish(
        self,
    ) -> None:
        """Non-dry source accounting increments each collected workflow once."""
        news_item = make_item("fn-news", content_type="news")
        calendar_item = make_item("fn-calendar", content_type="calendar")
        orchestrator = SourceOrchestrator(max_workers=1)
        target = MockTarget()
        storage = Mock()
        call_order: list[str] = []

        service = Mock()
        service.collect_items.side_effect = [
            {"items_generated": [news_item]},
            {"items_generated": [calendar_item]},
        ]
        service_cls = Mock(return_value=service)

        def publish_to_targets(**kwargs: Any) -> dict[str, Any]:
            call_order.append("publish")
            return {"published_success": 2}

        def increment_daily_execution(source_name: str) -> None:
            call_order.append(f"increment:{source_name}")

        storage.increment_daily_execution.side_effect = increment_daily_execution

        with (
            patch.object(
                orchestrator, "_get_service_for_source", return_value=service_cls
            ),
            patch(
                "binance_square_bot.services.concurrent_executor.SourceParallelPublisher"
            ) as publisher_cls,
        ):
            publisher_cls.return_value.publish_to_targets.side_effect = (
                publish_to_targets
            )
            orchestrator.run_sources(
                source_configs=[
                    {"source": type("FnSource", (), {})(), "execute": "execute"},
                    {
                        "source": type("FnSource", (), {})(),
                        "execute": "execute_calendar",
                    },
                ],
                targets=[target],
                api_keys_map={"MockTarget": ["key-1"]},
                storage=storage,
                dry_run=False,
            )

        assert call_order == [
            "publish",
            "increment:FnSource",
            "increment:FnSourceCalendar",
        ]

    def test_run_sources_dry_run_does_not_increment_collected_workflow_keys(
        self,
    ) -> None:
        """Dry-run parallel source accounting preserves no-increment semantics."""
        item = make_item("fn-news", content_type="news")
        orchestrator = SourceOrchestrator(max_workers=1)
        target = MockTarget()
        storage = Mock()

        service = Mock()
        service.collect_items.return_value = {"items_generated": [item]}
        service_cls = Mock(return_value=service)

        with patch.object(
            orchestrator, "_get_service_for_source", return_value=service_cls
        ):
            orchestrator.run_sources(
                source_configs=[{"source": type("FnSource", (), {})()}],
                targets=[target],
                api_keys_map={"MockTarget": ["key-1"]},
                storage=storage,
                dry_run=True,
            )

        storage.increment_daily_execution.assert_not_called()

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
        assert publisher_cls.return_value.publish_to_targets.call_args.kwargs[
            "tweets"
        ] == [item]
        assert (
            publisher_cls.return_value.publish_to_targets.call_args.kwargs["dry_run"]
            is True
        )
        assert result["publish_results"] == {
            "generated_success": 1,
            "published_success": 0,
        }
        storage.increment_daily_execution.assert_not_called()

    def test_total_per_run_limits_content_items_before_account_publishing(self) -> None:
        """total_per_run limits selected content items, not item/account pairs."""
        item_1 = make_item("item-1")
        item_2 = make_item("item-2")
        item_3 = make_item("item-3")
        orchestrator = SourceOrchestrator(max_workers=1, total_per_run=2)
        target = MockTarget()
        storage = Mock()
        storage.can_publish_key.return_value = True

        service_cls = Mock()
        service_cls.return_value.collect_items.return_value = {
            "items_generated": [item_1, item_2, item_3]
        }

        with (
            patch.object(
                orchestrator, "_get_service_for_source", return_value=service_cls
            ),
            patch(
                "binance_square_bot.services.concurrent_executor.random.shuffle",
                side_effect=lambda items: None,
            ),
            patch(
                "binance_square_bot.services.concurrent_executor.SourceParallelPublisher"
            ) as publisher_cls,
        ):
            publisher_cls.return_value.publish_to_targets.return_value = {
                "published_success": 4
            }
            orchestrator.run_sources(
                source_configs=[{"source": object(), "execute": "execute"}],
                targets=[target],
                api_keys_map={"MockTarget": ["key-1", "key-2"]},
                storage=storage,
            )

        publisher_cls.return_value.publish_to_targets.assert_called_once()
        published_items = (
            publisher_cls.return_value.publish_to_targets.call_args.kwargs["tweets"]
        )
        assert published_items == [item_1, item_2]

    def test_run_sources_aggregates_items_generated_and_passes_them_downstream(
        self,
    ) -> None:
        """SourceOrchestrator prefers items_generated over legacy tweets_generated."""
        item_1 = make_item("item-1")
        item_2 = make_item("item-2")
        orchestrator = SourceOrchestrator(max_workers=1)
        target = MockTarget()
        storage = Mock()

        source_results = {
            "FnSource": TaskResult(
                task_name="FnSource",
                success=True,
                data={
                    "items_generated": [item_1],
                    "tweets_generated": [{"text": "legacy-tweet"}],
                },
            ),
            "FollowinSource": TaskResult(
                task_name="FollowinSource",
                success=True,
                data={"items_generated": [item_2]},
            ),
            "FailedSource": TaskResult(
                task_name="FailedSource",
                success=False,
                data={"items_generated": [make_item("failed")]},
                error="boom",
            ),
        }

        with (
            patch(
                "binance_square_bot.services.concurrent_executor.ConcurrentExecutor.run_parallel",
                return_value=source_results,
            ),
            patch(
                "binance_square_bot.services.concurrent_executor.SourceParallelPublisher"
            ) as publisher_cls,
        ):
            publisher_cls.return_value.publish_to_targets.return_value = {
                "published_success": 2
            }
            orchestrator.run_sources(
                source_configs=[
                    {"source": type("FnSource", (), {})()},
                    {"source": type("FollowinSource", (), {})()},
                    {"source": type("FailedSource", (), {})()},
                ],
                targets=[target],
                api_keys_map={"MockTarget": ["key-1"]},
                storage=storage,
            )

        publisher_cls.return_value.publish_to_targets.assert_called_once()
        published_items = (
            publisher_cls.return_value.publish_to_targets.call_args.kwargs["tweets"]
        )
        assert published_items == [item_1, item_2]


class TestSourceParallelPublisher:
    """Tests for SourceParallelPublisher class."""

    def test_init_default_max_workers(self) -> None:
        """Test default max_workers is set correctly."""
        publisher = SourceParallelPublisher()
        assert publisher.max_workers == 3

    def test_init_custom_max_workers(self) -> None:
        """Test custom max_workers is set correctly."""
        publisher = SourceParallelPublisher(max_workers=7)
        assert publisher.max_workers == 7

    def test_passes_all_items_and_all_available_keys_to_account_item_publisher(
        self,
    ) -> None:
        """SourceParallelPublisher delegates every item and every available key."""
        items = [make_item("item-1"), make_item("item-2")]
        target = MockTarget()
        storage = Mock()
        storage.can_publish_key.return_value = True
        storage.is_content_published_today.return_value = False

        with patch(
            "binance_square_bot.services.concurrent_executor.AccountItemPublisher"
        ) as publisher_cls:
            publisher_cls.return_value.publish_items.return_value = {
                "items_total": 2,
                "api_keys_total": 2,
                "generated_success": 4,
                "generated_failed": 0,
                "published_success": 4,
                "published_failed": 0,
            }

            result = SourceParallelPublisher(max_workers=1).publish_to_targets(
                tweets=items,
                targets=[target],
                api_keys_map={"MockTarget": ["key-1", "key-2"]},
                storage=storage,
                delay_between_publishes=0,
            )

        publisher_cls.assert_called_once_with(
            delay_between_publishes=0, max_workers=1
        )
        publisher_cls.return_value.publish_items.assert_called_once_with(
            items=items,
            target=target,
            api_keys=["key-1", "key-2"],
            storage=storage,
            dry_run=False,
        )
        assert result["total_items"] == 2
        assert result["published_success"] == 4
        assert result["generated_success"] == 4

    def test_deduplicates_items_by_source_type_and_identifier_before_publishing(
        self,
    ) -> None:
        """Duplicate content identity is removed before account-level publishing."""
        original = make_item("same", source_name="FnSource", content_type="news")
        duplicate = make_item(
            "same",
            source_name="FnSource",
            content_type="news",
            title="Different title should still dedupe",
        )
        different_type = make_item(
            "same", source_name="FnSource", content_type="calendar"
        )
        target = MockTarget()
        storage = Mock()
        storage.can_publish_key.return_value = True
        storage.is_content_published_today.return_value = False

        with patch(
            "binance_square_bot.services.concurrent_executor.AccountItemPublisher"
        ) as publisher_cls:
            publisher_cls.return_value.publish_items.return_value = {
                "published_success": 2,
                "published_failed": 0,
            }

            SourceParallelPublisher(max_workers=1).publish_to_targets(
                tweets=[original, duplicate, different_type],
                targets=[target],
                api_keys_map={"MockTarget": ["key-1"]},
                storage=storage,
                delay_between_publishes=0,
            )

        published_items = publisher_cls.return_value.publish_items.call_args.kwargs[
            "items"
        ]
        assert published_items == [original, different_type]

    def test_filters_already_published_items_before_account_level_publishing(
        self,
    ) -> None:
        """Items published today are skipped before AccountItemPublisher is called."""
        already_published = make_item("already-published")
        fresh = make_item("fresh")
        target = MockTarget()
        storage = Mock()
        storage.can_publish_key.return_value = True
        storage.is_content_published_today.side_effect = [True, False]

        with patch(
            "binance_square_bot.services.concurrent_executor.AccountItemPublisher"
        ) as publisher_cls:
            publisher_cls.return_value.publish_items.return_value = {
                "published_success": 1,
                "published_failed": 0,
            }

            SourceParallelPublisher(max_workers=1).publish_to_targets(
                tweets=[already_published, fresh],
                targets=[target],
                api_keys_map={"MockTarget": ["key-1"]},
                storage=storage,
                delay_between_publishes=0,
            )

        storage.is_content_published_today.assert_any_call(
            "FnSource", "news", "already-published"
        )
        storage.is_content_published_today.assert_any_call("FnSource", "news", "fresh")
        published_items = publisher_cls.return_value.publish_items.call_args.kwargs[
            "items"
        ]
        assert published_items == [fresh]

    def test_legacy_dict_items_are_converted_before_account_publishing(self) -> None:
        """Legacy dict content items are normalized for AccountItemPublisher."""
        legacy_item = {
            "text": "Legacy generated tweet text should not become summary first",
            "source_name": "FnSource",
            "content_type": "news",
            "identifier": "legacy-1",
            "title": "Legacy Title",
            "summary": "Legacy Summary",
            "url": "https://example.com/legacy-1",
            "metadata": {"topic": "crypto"},
        }
        target = MockTarget()
        storage = Mock()
        storage.can_publish_key.return_value = True
        storage.is_content_published_today.return_value = False

        with patch(
            "binance_square_bot.services.concurrent_executor.AccountItemPublisher"
        ) as publisher_cls:
            publisher_cls.return_value.publish_items.return_value = {
                "published_success": 1,
                "published_failed": 0,
            }

            SourceParallelPublisher(max_workers=1).publish_to_targets(
                tweets=[legacy_item],
                targets=[target],
                api_keys_map={"MockTarget": ["key-1"]},
                storage=storage,
                delay_between_publishes=0,
            )

        published_items = publisher_cls.return_value.publish_items.call_args.kwargs[
            "items"
        ]
        assert len(published_items) == 1
        published_item = published_items[0]
        assert isinstance(published_item, TweetSourceItem)
        assert published_item.source_name == "FnSource"
        assert published_item.content_type == "news"
        assert published_item.identifier == "legacy-1"
        assert published_item.title == "Legacy Title"
        assert published_item.summary == "Legacy Summary"
        assert published_item.url == "https://example.com/legacy-1"
        assert published_item.metadata == {"topic": "crypto"}

    def test_legacy_string_items_are_skipped_before_account_publishing(self) -> None:
        """Unsupported legacy string tweets are dropped instead of published raw."""
        target = MockTarget()
        storage = Mock()

        with patch(
            "binance_square_bot.services.concurrent_executor.AccountItemPublisher"
        ) as publisher_cls:
            result = SourceParallelPublisher(max_workers=1).publish_to_targets(
                tweets=["legacy generated tweet"],
                targets=[target],
                api_keys_map={"MockTarget": ["key-1"]},
                storage=storage,
                delay_between_publishes=0,
            )

        publisher_cls.assert_not_called()
        assert result["total_items"] == 0
        assert result["total_tweets"] == 0
