from typing import Any
from unittest.mock import MagicMock, patch

from binance_square_bot.services.cli.followin_cli import FollowinCliService
from binance_square_bot.services.generation.models import TweetSourceItem
from binance_square_bot.services.source.followin_source import (
    FollowinToken,
    FollowinTopic,
)


class DummySourceConfig:
    daily_max_executions = 30


class DummySource:
    def __init__(self) -> None:
        self.config = DummySourceConfig()
        self.fetch = MagicMock(return_value=[])
        self.fetch_trending_topics = MagicMock(return_value=[])
        self.fetch_io_flow_tokens = MagicMock(return_value=[])
        self.fetch_discussion_tokens = MagicMock(return_value=[])
        self.generate = MagicMock(
            side_effect=AssertionError("source.generate must not be called")
        )
        self._generate_single_tweet = MagicMock(
            side_effect=AssertionError("_generate_single_tweet must not be called")
        )


class DummyTargetConfig:
    api_keys = ["api-key-1", "api-key-2"]
    daily_max_posts_per_key = 5


class DummyTarget:
    def __init__(self) -> None:
        self.config = DummyTargetConfig()
        self.filter = MagicMock()
        self.publish = MagicMock(
            side_effect=AssertionError("target.publish must not be called directly")
        )


class DummyStorage:
    def __init__(self) -> None:
        self.can_execute_source = MagicMock(return_value=True)
        self.is_content_published_today = MagicMock(return_value=False)
        self.increment_daily_execution = MagicMock()
        self.can_publish_key = MagicMock(return_value=True)
        self.mark_content_published = MagicMock()
        self.increment_daily_publish_count = MagicMock()


class PublisherFactory:
    def __init__(self, stats: dict[str, Any] | None = None) -> None:
        self.instance = MagicMock()
        self.instance.publish_items.return_value = stats or {
            "generated_success": 0,
            "generated_failed": 0,
            "published_success": 0,
            "published_failed": 0,
            "dry_run": False,
        }

    def __call__(self) -> MagicMock:
        return self.instance


def make_service(
    *,
    dry_run: bool = True,
    limit: int | None = 10,
    publisher_stats: dict[str, Any] | None = None,
) -> tuple[FollowinCliService, DummySource, DummyTarget, DummyStorage, MagicMock]:
    source = DummySource()
    target = DummyTarget()
    storage = DummyStorage()
    if publisher_stats is None:
        publisher_stats = {
            "generated_success": 0,
            "generated_failed": 0,
            "published_success": 0,
            "published_failed": 0,
            "dry_run": dry_run,
        }
    publisher_factory = PublisherFactory(publisher_stats)

    with (
        patch(
            "binance_square_bot.services.cli.followin_cli.StorageService",
            return_value=storage,
        ),
        patch(
            "binance_square_bot.services.cli.followin_cli.FollowinSource",
            return_value=source,
        ),
        patch(
            "binance_square_bot.services.cli.followin_cli.BinanceTarget",
            return_value=target,
        ),
        patch(
            "binance_square_bot.services.cli.followin_cli.AccountItemPublisher",
            new=publisher_factory,
            create=True,
        ),
    ):
        service = FollowinCliService(dry_run=dry_run, limit=limit)

    return service, source, target, storage, publisher_factory.instance


def test_followin_cli_service_init() -> None:
    service, _, _, _, _ = make_service(dry_run=True, limit=5)

    assert service.dry_run is True
    assert service.limit == 5


def test_publish_items_uses_publisher_and_maps_topic_content_type() -> None:
    publisher_stats = {
        "generated_success": 2,
        "published_success": 1,
        "dry_run": False,
    }
    service, source, target, storage, publisher = make_service(
        dry_run=False,
        limit=10,
        publisher_stats=publisher_stats,
    )
    topic = FollowinTopic(
        id=1,
        title="Topic 1",
        summary="Summary 1",
        url="https://followin.io/topic/1",
    )

    result = service._publish_items([topic], "FollowinSourceTopics", "Trending Topics")

    source.generate.assert_not_called()
    source._generate_single_tweet.assert_not_called()
    target.publish.assert_not_called()
    publisher.publish_items.assert_called_once()
    items, publish_target, api_keys, publish_storage = (
        publisher.publish_items.call_args.args
    )
    assert publish_target is target
    assert api_keys == target.config.api_keys
    assert publish_storage is storage
    assert publisher.publish_items.call_args.kwargs == {"dry_run": False}
    assert items == [
        TweetSourceItem(
            source_name="FollowinSource",
            content_type="topics",
            identifier="1",
            title="Topic 1",
            summary="Summary 1",
            url="https://followin.io/topic/1",
        )
    ]
    assert result["items_fetched"] == 1
    assert result["items_generated"] == items
    assert result["dry_run"] is False
    assert result["generated_success"] == 2
    assert result["published_success"] == 1
    storage.increment_daily_execution.assert_called_once_with("FollowinSourceTopics")


def test_io_flow_and_discussion_token_content_types_are_preserved() -> None:
    service, _, _, storage, publisher = make_service(dry_run=False, limit=10)
    io_flow_token = FollowinToken(
        id=101,
        name="IO Token",
        symbol="IO",
        summary="IO summary",
        token_quote={"price": 1.23},
        category="io_flow",
    )
    discussion_token = FollowinToken(
        id=201,
        name="Discussion Token",
        symbol="DISC",
        summary="Discussion summary",
        category="discussion",
    )

    io_result = service._publish_items(
        [io_flow_token], "FollowinSourceIOFlow", "IO Flow Tokens"
    )
    discussion_result = service._publish_items(
        [discussion_token], "FollowinSourceDiscussion", "Discussion Tokens"
    )

    io_items = publisher.publish_items.call_args_list[0].args[0]
    discussion_items = publisher.publish_items.call_args_list[1].args[0]
    assert io_items == [
        TweetSourceItem(
            source_name="FollowinSource",
            content_type="io_flow",
            identifier="101",
            title="IO Token ($IO)",
            summary="IO summary",
            coin_tags=["IO"],
            metadata={
                "name": "IO Token",
                "symbol": "IO",
                "category": "io_flow",
                "token_quote": {"price": 1.23},
            },
        )
    ]
    assert discussion_items == [
        TweetSourceItem(
            source_name="FollowinSource",
            content_type="discussion",
            identifier="201",
            title="Discussion Token ($DISC)",
            summary="Discussion summary",
            coin_tags=["DISC"],
            metadata={
                "name": "Discussion Token",
                "symbol": "DISC",
                "category": "discussion",
                "token_quote": None,
            },
        )
    ]
    assert io_result["items_generated"] == io_items
    assert discussion_result["items_generated"] == discussion_items
    storage.increment_daily_execution.assert_any_call("FollowinSourceIOFlow")
    storage.increment_daily_execution.assert_any_call("FollowinSourceDiscussion")


def test_publish_items_filters_before_limit() -> None:
    service, _, _, storage, publisher = make_service(dry_run=True, limit=2)
    items = [
        FollowinTopic(id=1, title="Published 1", summary="Summary 1", url="https://test/1"),
        FollowinTopic(id=2, title="Published 2", summary="Summary 2", url="https://test/2"),
        FollowinTopic(id=3, title="Fresh 3", summary="Summary 3", url="https://test/3"),
        FollowinTopic(id=4, title="Fresh 4", summary="Summary 4", url="https://test/4"),
        FollowinTopic(id=5, title="Fresh 5", summary="Summary 5", url="https://test/5"),
    ]
    storage.is_content_published_today.side_effect = (
        lambda source_name, content_type, identifier: identifier in {"1", "2"}
    )

    result = service._publish_items(items, "FollowinSourceTopics", "Trending Topics")

    publisher_items = publisher.publish_items.call_args.args[0]
    assert [item.identifier for item in publisher_items] == ["3", "4"]
    assert result["items_fetched"] == 2
    assert result["items_generated"] == publisher_items
    storage.is_content_published_today.assert_any_call("FollowinSource", "topics", "1")
    storage.is_content_published_today.assert_any_call("FollowinSource", "topics", "5")


def test_execute_full_workflow_uses_skill_selectable_content_types() -> None:
    service, source, _, storage, publisher = make_service(dry_run=False, limit=10)
    topic = FollowinTopic(
        id=1,
        title="Topic",
        summary="Topic summary",
        url="https://test/topic",
    )
    io_flow_token = FollowinToken(
        id=2,
        name="IO Token",
        symbol="IO",
        summary="IO summary",
        category="io_flow",
    )
    discussion_token = FollowinToken(
        id=3,
        name="Discussion Token",
        symbol="DISC",
        summary="Discussion summary",
        category="discussion",
    )
    source.fetch.return_value = [topic, io_flow_token, discussion_token]

    result = service.execute()

    source.generate.assert_not_called()
    publisher.publish_items.assert_called_once()
    items = publisher.publish_items.call_args.args[0]
    assert [item.content_type for item in items] == ["topics", "io_flow", "discussion"]
    assert "unknown" not in {item.content_type for item in items}
    assert result["items_fetched"] == 3
    assert result["items_generated"] == items
    storage.can_execute_source.assert_called_once_with("FollowinSource", 30)
    storage.is_content_published_today.assert_any_call("FollowinSource", "topics", "1")
    storage.is_content_published_today.assert_any_call("FollowinSource", "io_flow", "2")
    storage.is_content_published_today.assert_any_call(
        "FollowinSource", "discussion", "3"
    )
    storage.increment_daily_execution.assert_called_once_with("FollowinSource")


def test_execute_topics_fetches_and_publishes_topics() -> None:
    service, source, _, storage, publisher = make_service(dry_run=False, limit=10)
    topic = FollowinTopic(
        id=1,
        title="Topic",
        summary="Summary",
        url="https://test/topic",
    )
    source.fetch_trending_topics.return_value = [topic]

    result = service.execute_topics()

    publisher.publish_items.assert_called_once()
    assert publisher.publish_items.call_args.args[0][0].content_type == "topics"
    assert result["items_fetched"] == 1
    storage.can_execute_source.assert_called_once_with("FollowinSourceTopics", 30)
    storage.increment_daily_execution.assert_called_once_with("FollowinSourceTopics")


def test_dry_run_passes_dry_run_true_without_execution_increment() -> None:
    service, source, target, storage, publisher = make_service(dry_run=True, limit=10)
    topic = FollowinTopic(
        id=1,
        title="Dry topic",
        summary="Dry summary",
        url="https://test/dry",
    )
    source.fetch_trending_topics.return_value = [topic]

    result = service.execute_topics()

    publisher.publish_items.assert_called_once()
    assert publisher.publish_items.call_args.args[2] == target.config.api_keys
    assert publisher.publish_items.call_args.kwargs == {"dry_run": True}
    assert result["dry_run"] is True
    storage.increment_daily_execution.assert_not_called()


def test_no_api_keys_non_dry_returns_without_publisher_or_increment() -> None:
    service, source, target, storage, publisher = make_service(dry_run=False, limit=10)
    target.config.api_keys = []
    topic = FollowinTopic(
        id=1,
        title="No key topic",
        summary="No key summary",
        url="https://test/no-key",
    )
    source.fetch_trending_topics.return_value = [topic]

    result = service.execute_topics()

    source.generate.assert_not_called()
    publisher.publish_items.assert_not_called()
    storage.increment_daily_execution.assert_not_called()
    assert result == {
        "items_fetched": 1,
        "items_generated": [
            TweetSourceItem(
                source_name="FollowinSource",
                content_type="topics",
                identifier="1",
                title="No key topic",
                summary="No key summary",
                url="https://test/no-key",
            )
        ],
        "dry_run": False,
    }


def test_execute_daily_limit_reached_returns_items_stats() -> None:
    service, source, _, storage, publisher = make_service(dry_run=True, limit=10)
    storage.can_execute_source.return_value = False

    result = service.execute()

    source.generate.assert_not_called()
    publisher.publish_items.assert_not_called()
    assert result["items_fetched"] == 0
    assert result["items_generated"] == []


def test_execute_topics_daily_limit_reached_returns_items_stats() -> None:
    service, source, _, storage, publisher = make_service(dry_run=True, limit=10)
    storage.can_execute_source.return_value = False

    result = service.execute_topics()

    source.generate.assert_not_called()
    publisher.publish_items.assert_not_called()
    assert result["items_fetched"] == 0
    assert result["items_generated"] == []


def test_execute_io_flow_daily_limit_reached_returns_items_stats() -> None:
    service, source, _, storage, publisher = make_service(dry_run=True, limit=10)
    storage.can_execute_source.return_value = False

    result = service.execute_io_flow()

    source.generate.assert_not_called()
    publisher.publish_items.assert_not_called()
    assert result["items_fetched"] == 0
    assert result["items_generated"] == []


def test_execute_discussion_daily_limit_reached_returns_items_stats() -> None:
    service, source, _, storage, publisher = make_service(dry_run=True, limit=10)
    storage.can_execute_source.return_value = False

    result = service.execute_discussion()

    source.generate.assert_not_called()
    publisher.publish_items.assert_not_called()
    assert result["items_fetched"] == 0
    assert result["items_generated"] == []


def test_execute_topics_empty_items_returns_items_stats() -> None:
    service, source, _, storage, publisher = make_service(dry_run=True)
    source.fetch_trending_topics.return_value = []

    result = service.execute_topics()

    publisher.publish_items.assert_not_called()
    storage.increment_daily_execution.assert_not_called()
    assert result["items_fetched"] == 0
    assert result["items_generated"] == []


def test_execute_io_flow_empty_items_returns_items_stats() -> None:
    service, source, _, storage, publisher = make_service(dry_run=True)
    source.fetch_io_flow_tokens.return_value = []

    result = service.execute_io_flow()

    publisher.publish_items.assert_not_called()
    storage.increment_daily_execution.assert_not_called()
    assert result["items_fetched"] == 0
    assert result["items_generated"] == []


def test_execute_discussion_empty_items_returns_items_stats() -> None:
    service, source, _, storage, publisher = make_service(dry_run=True)
    source.fetch_discussion_tokens.return_value = []

    result = service.execute_discussion()

    publisher.publish_items.assert_not_called()
    storage.increment_daily_execution.assert_not_called()
    assert result["items_fetched"] == 0
    assert result["items_generated"] == []


def test_publish_items_no_items_returns_empty_stats_without_publisher() -> None:
    service, _, _, storage, publisher = make_service(dry_run=True)

    result = service._publish_items([], "FollowinSourceTopics", "Trending Topics")

    publisher.publish_items.assert_not_called()
    storage.increment_daily_execution.assert_not_called()
    assert result == {"items_fetched": 0, "items_generated": [], "dry_run": True}
