from datetime import datetime
from typing import Any
from unittest.mock import MagicMock, patch

from binance_square_bot.services.cli.fn_cli import FnCliService
from binance_square_bot.services.generation.models import TweetSourceItem
from binance_square_bot.services.source.fn_source import (
    AirdropEvent,
    Article,
    CalendarEvent,
    FundraisingEvent,
)


class DummySourceConfig:
    daily_max_executions = 30


class DummySource:
    def __init__(self) -> None:
        self.config = DummySourceConfig()
        self.fetch = MagicMock(return_value=[])
        self.fetch_calendar = MagicMock(return_value=[])
        self.fetch_airdrops = MagicMock(return_value=[])
        self.fetch_fundraising = MagicMock(return_value=[])
        self.generate = MagicMock(
            side_effect=AssertionError("source.generate must not be called")
        )
        self.generate_calendar = MagicMock(
            side_effect=AssertionError("source.generate_calendar must not be called")
        )
        self.generate_airdrops = MagicMock(
            side_effect=AssertionError("source.generate_airdrops must not be called")
        )
        self.generate_fundraising = MagicMock(
            side_effect=AssertionError("source.generate_fundraising must not be called")
        )


class DummyTargetConfig:
    api_keys = ["api-key-1", "api-key-2"]
    daily_max_posts_per_key = 5


class DummyTarget:
    def __init__(self) -> None:
        self.config = DummyTargetConfig()
        self.filter = MagicMock()
        self.publish = MagicMock()


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
) -> tuple[FnCliService, DummySource, DummyTarget, DummyStorage, MagicMock]:
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
            "binance_square_bot.services.cli.fn_cli.StorageService",
            return_value=storage,
        ),
        patch(
            "binance_square_bot.services.cli.fn_cli.FnSource",
            return_value=source,
        ),
        patch(
            "binance_square_bot.services.cli.fn_cli.BinanceTarget",
            return_value=target,
        ),
        patch(
            "binance_square_bot.services.cli.fn_cli.AccountItemPublisher",
            new=publisher_factory,
            create=True,
        ),
    ):
        service = FnCliService(dry_run=dry_run, limit=limit)

    return service, source, target, storage, publisher_factory.instance


def test_fn_cli_service_init() -> None:
    """Test FnCliService can be initialized without real source/target side effects."""
    service, _, _, _, _ = make_service(dry_run=True, limit=5)

    assert service.dry_run is True
    assert service.limit == 5


def test_execute_uses_account_item_publisher_with_filtered_mapped_articles() -> None:
    publisher_stats = {"generated_success": 2, "published_failed": 1, "dry_run": False}
    service, source, target, storage, publisher = make_service(
        dry_run=False,
        limit=1,
        publisher_stats=publisher_stats,
    )
    old_article = Article(
        title="Old article",
        url="https://example.com/old",
        content="Old summary",
        published_at=datetime(2026, 6, 1, 8, 0),
    )
    new_article = Article(
        title="New article",
        url="https://example.com/new",
        content="New summary",
        published_at=datetime(2026, 6, 1, 9, 0),
    )
    extra_article = Article(
        title="Extra article",
        url="https://example.com/extra",
        content="Extra summary",
    )
    source.fetch.return_value = [old_article, new_article, extra_article]
    storage.is_content_published_today.side_effect = (
        lambda source_name, content_type, identifier: identifier == old_article.url
    )

    result = service.execute()

    source.generate.assert_not_called()
    publisher.publish_items.assert_called_once()
    items, publish_target, api_keys, publish_storage = (
        publisher.publish_items.call_args.args
    )
    assert publish_target is target
    assert api_keys == target.config.api_keys
    assert publish_storage is storage
    assert publisher.publish_items.call_args.kwargs == {"dry_run": False}
    assert new_article.published_at is not None
    assert items == [
        TweetSourceItem(
            source_name="FnSource",
            content_type="news",
            identifier=new_article.url,
            title=new_article.title,
            summary=new_article.content,
            url=new_article.url,
            metadata={"published_at": new_article.published_at.isoformat()},
        )
    ]
    assert result["items_fetched"] == 1
    assert result["items_generated"] == items
    assert result["dry_run"] is False
    assert result["generated_success"] == 2
    assert result["published_failed"] == 1
    storage.increment_daily_execution.assert_called_once_with("FnSource")


def test_execute_dry_run_calls_publisher_without_increment() -> None:
    service, source, target, storage, publisher = make_service(dry_run=True, limit=10)
    article = Article(
        title="Dry run article",
        url="https://example.com/dry",
        content="Dry run summary",
    )
    source.fetch.return_value = [article]

    result = service.execute()

    source.generate.assert_not_called()
    publisher.publish_items.assert_called_once()
    assert publisher.publish_items.call_args.kwargs == {"dry_run": True}
    items, publish_target, api_keys, publish_storage = (
        publisher.publish_items.call_args.args
    )
    assert publish_target is target
    assert api_keys == target.config.api_keys
    assert publish_storage is storage
    assert result["items_fetched"] == 1
    assert result["items_generated"] == items
    assert result["dry_run"] is True
    storage.increment_daily_execution.assert_not_called()


def test_execute_calendar_filters_maps_content_type_and_publishes_items() -> None:
    service, source, _, storage, publisher = make_service(dry_run=False, limit=10)
    published = CalendarEvent(
        title="Published calendar",
        url="https://example.com/calendar-published",
        description="Already published event",
        category=1,
    )
    fresh = CalendarEvent(
        title="Fresh calendar",
        url="https://example.com/calendar-fresh",
        description="Fresh event",
        start_time=datetime(2026, 6, 2, 10, 0),
        end_time=datetime(2026, 6, 2, 11, 0),
        category=2,
    )
    source.fetch_calendar.return_value = [published, fresh]
    storage.is_content_published_today.side_effect = (
        lambda source_name, content_type, identifier: identifier == published.url
    )

    result = service.execute_calendar()

    source.generate_calendar.assert_not_called()
    storage.is_content_published_today.assert_any_call(
        "FnSource", "calendar", published.url
    )
    storage.is_content_published_today.assert_any_call(
        "FnSource", "calendar", fresh.url
    )
    items = publisher.publish_items.call_args.args[0]
    assert fresh.start_time is not None
    assert fresh.end_time is not None
    assert items == [
        TweetSourceItem(
            source_name="FnSource",
            content_type="calendar",
            identifier=fresh.url,
            title=fresh.title,
            summary=fresh.description,
            url=fresh.url,
            metadata={
                "start_time": fresh.start_time.isoformat(),
                "end_time": fresh.end_time.isoformat(),
                "category": fresh.category,
            },
        )
    ]
    assert result["items_fetched"] == 1
    assert result["items_generated"] == items
    storage.increment_daily_execution.assert_called_once_with("FnSourceCalendar")


def test_execute_airdrops_filters_maps_content_type_and_publishes_items() -> None:
    service, source, _, storage, publisher = make_service(dry_run=False, limit=10)
    published = AirdropEvent(
        id=1,
        title="Published airdrop",
        url="https://example.com/airdrop-published",
        brief="Already published airdrop",
    )
    fresh = AirdropEvent(
        id=2,
        title="Fresh airdrop",
        url="https://example.com/airdrop-fresh",
        brief="Fresh airdrop",
        published_at=datetime(2026, 6, 3, 12, 0),
    )
    source.fetch_airdrops.return_value = [published, fresh]
    storage.is_content_published_today.side_effect = (
        lambda source_name, content_type, identifier: identifier == published.url
    )

    result = service.execute_airdrops()

    source.generate_airdrops.assert_not_called()
    storage.is_content_published_today.assert_any_call(
        "FnSource", "airdrop", published.url
    )
    storage.is_content_published_today.assert_any_call("FnSource", "airdrop", fresh.url)
    items = publisher.publish_items.call_args.args[0]
    assert fresh.published_at is not None
    assert items == [
        TweetSourceItem(
            source_name="FnSource",
            content_type="airdrop",
            identifier=fresh.url,
            title=fresh.title,
            summary=fresh.brief,
            url=fresh.url,
            metadata={"id": fresh.id, "published_at": fresh.published_at.isoformat()},
        )
    ]
    assert result["items_fetched"] == 1
    assert result["items_generated"] == items
    storage.increment_daily_execution.assert_called_once_with("FnSourceAirdrops")


def test_execute_fundraising_filters_maps_content_type_and_publishes_items() -> None:
    service, source, _, storage, publisher = make_service(dry_run=False, limit=10)
    published = FundraisingEvent(
        id=1,
        project_name="Published project",
        amount=1.0,
        round_str="Seed",
        description="Already published fundraising",
        investors=["Investor A"],
        url="https://example.com/fundraising-published",
    )
    fresh = FundraisingEvent(
        id=2,
        project_name="Fresh project",
        amount=2.5,
        round_str="Series A",
        description="Fresh fundraising",
        investors=["Investor B"],
        url="https://example.com/fundraising-fresh",
        date=datetime(2026, 6, 4, 13, 0),
    )
    source.fetch_fundraising.return_value = [published, fresh]
    storage.is_content_published_today.side_effect = (
        lambda source_name, content_type, identifier: identifier == published.url
    )

    result = service.execute_fundraising()

    source.generate_fundraising.assert_not_called()
    storage.is_content_published_today.assert_any_call(
        "FnSource", "fundraising", published.url
    )
    storage.is_content_published_today.assert_any_call(
        "FnSource", "fundraising", fresh.url
    )
    items = publisher.publish_items.call_args.args[0]
    assert fresh.date is not None
    assert items == [
        TweetSourceItem(
            source_name="FnSource",
            content_type="fundraising",
            identifier=fresh.url,
            title=fresh.project_name,
            summary=fresh.description,
            url=fresh.url,
            metadata={
                "id": fresh.id,
                "amount": fresh.amount,
                "round": fresh.round_str,
                "investors": fresh.investors,
                "date": fresh.date.isoformat(),
            },
        )
    ]
    assert result["items_fetched"] == 1
    assert result["items_generated"] == items
    storage.increment_daily_execution.assert_called_once_with("FnSourceFundraising")


def test_execute_without_api_keys_returns_stats_without_publishing_or_increment() -> (
    None
):
    service, source, target, storage, publisher = make_service(dry_run=False, limit=10)
    target.config.api_keys = []
    article = Article(
        title="No key article",
        url="https://example.com/no-key",
        content="No key summary",
    )
    source.fetch.return_value = [article]

    result = service.execute()

    source.generate.assert_not_called()
    publisher.publish_items.assert_not_called()
    storage.increment_daily_execution.assert_not_called()
    assert result == {
        "items_fetched": 1,
        "items_generated": [
            TweetSourceItem(
                source_name="FnSource",
                content_type="news",
                identifier=article.url,
                title=article.title,
                summary=article.content,
                url=article.url,
                metadata={"published_at": None},
            )
        ],
        "dry_run": False,
    }
