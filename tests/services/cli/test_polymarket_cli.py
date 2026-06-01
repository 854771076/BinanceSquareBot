from typing import Any
from unittest.mock import MagicMock, patch

from binance_square_bot.services.cli.polymarket_cli import PolymarketCliService
from binance_square_bot.services.generation.models import TweetSourceItem
from binance_square_bot.services.source.polymarket_source import PolymarketMarket


class DummySourceConfig:
    min_volume_threshold = 1_000.0
    min_win_rate = 0.6
    max_win_rate = 0.95
    daily_max_executions = 10


class DummySource:
    def __init__(self) -> None:
        self.config = DummySourceConfig()
        self.fetch = MagicMock(return_value=[])
        self.generate = MagicMock(
            side_effect=AssertionError("source.generate must not be called")
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
        self.increment_daily_execution = MagicMock()
        self.can_publish_key = MagicMock(return_value=True)
        self.is_content_published_today = MagicMock(return_value=False)
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
    publisher_stats: dict[str, Any] | None = None,
) -> tuple[PolymarketCliService, DummySource, DummyTarget, DummyStorage, MagicMock]:
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
            "binance_square_bot.services.cli.polymarket_cli.StorageService",
            return_value=storage,
        ),
        patch(
            "binance_square_bot.services.cli.polymarket_cli.PolymarketSource",
            return_value=source,
        ),
        patch(
            "binance_square_bot.services.cli.polymarket_cli.BinanceTarget",
            return_value=target,
        ),
        patch(
            "binance_square_bot.services.cli.polymarket_cli.AccountItemPublisher",
            new=publisher_factory,
            create=True,
        ),
    ):
        service = PolymarketCliService(dry_run=dry_run)

    return service, source, target, storage, publisher_factory.instance


def market(
    condition_id: str,
    *,
    question: str | None = None,
    yes_price: float = 0.7,
    no_price: float = 0.3,
    volume: float = 2_000.0,
    description: str | None = None,
    image: str | None = None,
) -> PolymarketMarket:
    return PolymarketMarket(
        condition_id=condition_id,
        question=question or f"Market {condition_id}",
        yes_price=yes_price,
        no_price=no_price,
        volume=volume,
        description=description,
        image=image,
    )


def test_polymarket_cli_service_init() -> None:
    """Test PolymarketCliService can be initialized without real side effects."""
    service, _, _, _, _ = make_service(dry_run=True)

    assert service.dry_run is True


def test_execute_uses_publisher_with_mapped_candidates_and_dry_run() -> None:
    publisher_stats = {
        "generated_success": 2,
        "published_success": 0,
        "dry_run": True,
    }
    service, source, target, storage, publisher = make_service(
        dry_run=True,
        publisher_stats=publisher_stats,
    )
    candidate = market(
        "candidate-1",
        question="Will BTC hit a new high?",
        yes_price=0.72,
        no_price=0.28,
        volume=5_000.0,
        description="Bitcoin all-time high market",
        image="https://example.com/btc.png",
    )
    source.fetch.return_value = [candidate]

    result = service.execute()

    source.generate.assert_not_called()
    target.publish.assert_not_called()
    publisher.publish_items.assert_called_once()
    items, publish_target, api_keys, publish_storage = (
        publisher.publish_items.call_args.args
    )
    assert publish_target is target
    assert api_keys == target.config.api_keys
    assert publish_storage is storage
    assert publisher.publish_items.call_args.kwargs == {"dry_run": True}
    assert items == [
        TweetSourceItem(
            source_name="PolymarketSource",
            content_type="polymarket_research",
            identifier="candidate-1",
            title="Will BTC hit a new high?",
            summary="Bitcoin all-time high market",
            metadata={
                "condition_id": "candidate-1",
                "yes_price": 0.72,
                "no_price": 0.28,
                "volume": 5_000.0,
                "image": "https://example.com/btc.png",
            },
        )
    ]
    assert result["markets_fetched"] == 1
    assert result["items_fetched"] == 1
    assert result["items_generated"] == items
    assert result["dry_run"] is True
    assert result["generated_success"] == 2
    storage.increment_daily_execution.assert_not_called()


def test_execute_filters_sorts_candidates_by_volume_and_limits_to_top_five() -> None:
    service, source, _, _, publisher = make_service(dry_run=True)
    valid_markets = [
        market("valid-1", volume=1_500.0, yes_price=0.61, no_price=0.39),
        market("valid-2", volume=9_000.0, yes_price=0.7, no_price=0.3),
        market("valid-3", volume=3_000.0, yes_price=0.4, no_price=0.6),
        market("valid-4", volume=7_000.0, yes_price=0.65, no_price=0.35),
        market("valid-5", volume=4_000.0, yes_price=0.2, no_price=0.8),
        market("valid-6", volume=6_000.0, yes_price=0.94, no_price=0.06),
    ]
    source.fetch.return_value = [
        market("too-small", volume=999.0, yes_price=0.9, no_price=0.1),
        market("too-balanced", volume=8_000.0, yes_price=0.55, no_price=0.45),
        market("too-certain", volume=10_000.0, yes_price=0.96, no_price=0.97),
        *valid_markets,
    ]

    result = service.execute()

    source.generate.assert_not_called()
    publisher.publish_items.assert_called_once()
    items = publisher.publish_items.call_args.args[0]
    assert [item.identifier for item in items] == [
        "valid-2",
        "valid-4",
        "valid-6",
        "valid-5",
        "valid-3",
    ]
    assert result["markets_fetched"] == 9
    assert result["items_fetched"] == 5
    assert result["items_generated"] == items


def test_execute_filters_already_published_markets_before_mapping() -> None:
    service, source, _, storage, publisher = make_service(dry_run=True)
    published_market = market("published-1", volume=9_000.0)
    unpublished_market = market("unpublished-1", volume=8_000.0)
    source.fetch.return_value = [published_market, unpublished_market]
    storage.is_content_published_today.side_effect = (
        lambda source_name, content_type, identifier: identifier == "published-1"
    )

    result = service.execute()

    publisher.publish_items.assert_called_once()
    items = publisher.publish_items.call_args.args[0]
    assert [item.identifier for item in items] == ["unpublished-1"]
    assert result["markets_fetched"] == 2
    assert result["items_fetched"] == 1
    assert result["items_generated"] == items
    assert storage.is_content_published_today.call_args_list == [
        (("PolymarketSource", "polymarket_research", "published-1"),),
        (("PolymarketSource", "polymarket_research", "unpublished-1"),),
    ]


def test_execute_daily_limit_reached_returns_items_stats() -> None:
    service, source, _, storage, publisher = make_service(dry_run=True)
    storage.can_execute_source.return_value = False

    result = service.execute()

    source.generate.assert_not_called()
    publisher.publish_items.assert_not_called()
    assert result["items_fetched"] == 0
    assert result["items_generated"] == []


def test_collect_items_daily_limit_reached_returns_error_empty_items() -> None:
    service, source, _, storage, _ = make_service(dry_run=False)
    storage.can_execute_source.return_value = False

    result = service.collect_items()

    storage.can_execute_source.assert_called_once_with("PolymarketSource", 10)
    source.fetch.assert_not_called()
    assert result["error"] == "daily limit reached"
    assert result["items_fetched"] == 0
    assert result["items_generated"] == []


def test_execute_no_candidate_markets_returns_empty_items_stats() -> None:
    service, source, _, storage, publisher = make_service(dry_run=True)
    source.fetch.return_value = [
        market("too-small", volume=999.0, yes_price=0.9, no_price=0.1),
        market("too-balanced", volume=8_000.0, yes_price=0.55, no_price=0.45),
    ]

    result = service.execute()

    source.generate.assert_not_called()
    publisher.publish_items.assert_not_called()
    storage.increment_daily_execution.assert_not_called()
    assert result["markets_fetched"] == 2
    assert result["items_fetched"] == 0
    assert result["items_generated"] == []


def test_execute_non_dry_without_api_keys_skips_publish_and_increment() -> None:
    service, source, target, storage, publisher = make_service(dry_run=False)
    target.config.api_keys = []
    source.fetch.return_value = [market("candidate-1", volume=2_000.0)]

    result = service.execute()

    source.generate.assert_not_called()
    publisher.publish_items.assert_not_called()
    storage.increment_daily_execution.assert_not_called()
    assert result["markets_fetched"] == 1
    assert result["items_fetched"] == 1
    assert result["items_generated"][0].identifier == "candidate-1"
    assert result["dry_run"] is False


def test_execute_non_dry_increments_daily_execution_after_publisher_returns() -> None:
    service, source, _, storage, publisher = make_service(
        dry_run=False,
        publisher_stats={
            "generated_success": 1,
            "published_success": 1,
            "dry_run": False,
        },
    )
    source.fetch.return_value = [market("candidate-1", volume=2_000.0)]
    call_order: list[str] = []
    def publish_items(*args: Any, **kwargs: Any) -> dict[str, Any]:
        call_order.append("publish")
        return {"generated_success": 1, "published_success": 1, "dry_run": False}

    def increment_daily_execution(source_name: str) -> None:
        call_order.append(f"increment:{source_name}")

    publisher.publish_items.side_effect = publish_items
    storage.increment_daily_execution.side_effect = increment_daily_execution

    result = service.execute()

    publisher.publish_items.assert_called_once()
    storage.increment_daily_execution.assert_called_once_with("PolymarketSource")
    assert call_order == ["publish", "increment:PolymarketSource"]
    assert result["generated_success"] == 1
    assert result["published_success"] == 1


def test_execute_does_not_call_source_generate() -> None:
    service, source, _, _, publisher = make_service(dry_run=True)
    source.fetch.return_value = [market("candidate-1", volume=2_000.0)]

    service.execute()

    source.generate.assert_not_called()
    publisher.publish_items.assert_called_once()
