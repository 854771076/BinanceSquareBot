from typing import Any

from loguru import logger
from rich.console import Console
from rich.table import Table

from binance_square_bot.services.account_item_publisher import AccountItemPublisher
from binance_square_bot.services.generation.mappers import followin_item_to_item
from binance_square_bot.services.generation.models import TweetSourceItem
from binance_square_bot.services.source.followin_source import (
    FollowinSource,
    FollowinToken,
    FollowinTopic,
)
from binance_square_bot.services.storage import StorageService
from binance_square_bot.services.target.binance_target import BinanceTarget

console = Console()


class FollowinCliService:
    """CLI business logic for Followin workflow."""

    def __init__(self, dry_run: bool = False, limit: int | None = None) -> None:
        self.dry_run = dry_run
        self.limit = limit
        self.storage = StorageService()
        self.source = FollowinSource()  # type: ignore[no-untyped-call]
        self.target = BinanceTarget()  # type: ignore[no-untyped-call]
        self.publisher = AccountItemPublisher()

    def execute(self) -> dict[str, Any]:
        """Execute the full crawl-generate-publish workflow.

        Returns:
            Dictionary with execution statistics
        """
        logger.info("Starting Followin workflow")

        # Check execution limit
        storage_key = "FollowinSource"
        if not self.storage.can_execute_source(
            storage_key, self.source.config.daily_max_executions
        ):
            console.print(
                "[yellow]⚠️ Daily execution limit reached for FollowinSource[/yellow]"
            )
            return {**self._empty_stats(), "error": "daily limit reached"}

        # Fetch items
        console.print("[blue]Fetching Followin data...[/blue]")
        items = self.source.fetch()
        console.print(f"✓ Fetched {len(items)} items (topics + tokens)")

        result = self._publish_items(items, storage_key, "Followin")
        self._print_summary(result, "Followin")
        logger.info(f"Followin workflow complete: {result}")
        return result

    def execute_topics(self) -> dict[str, Any]:
        """Execute trending topics workflow."""
        logger.info("Starting Followin trending topics workflow")

        storage_key = "FollowinSourceTopics"
        if not self.storage.can_execute_source(
            storage_key, self.source.config.daily_max_executions
        ):
            console.print(
                "[yellow]⚠️ Daily limit reached for Followin trending topics[/yellow]"
            )
            return {**self._empty_stats(), "error": "daily limit reached"}

        console.print("[blue]Fetching Followin trending topics...[/blue]")
        items = self.source.fetch_trending_topics()
        console.print(f"✓ Fetched {len(items)} trending topics")

        result = self._publish_items(items, storage_key, "Trending Topics")
        self._print_summary(result, "Trending Topics")
        logger.info(f"Followin trending topics workflow complete: {result}")
        return result

    def execute_io_flow(self) -> dict[str, Any]:
        """Execute IO flow tokens workflow."""
        logger.info("Starting Followin IO flow tokens workflow")

        storage_key = "FollowinSourceIOFlow"
        if not self.storage.can_execute_source(
            storage_key, self.source.config.daily_max_executions
        ):
            console.print("[yellow]⚠️ Daily limit reached for Followin IO flow[/yellow]")
            return {**self._empty_stats(), "error": "daily limit reached"}

        console.print("[blue]Fetching Followin IO flow tokens...[/blue]")
        items = self.source.fetch_io_flow_tokens()
        console.print(f"✓ Fetched {len(items)} IO flow tokens")

        result = self._publish_items(items, storage_key, "IO Flow Tokens")
        self._print_summary(result, "IO Flow Tokens")
        logger.info(f"Followin IO flow workflow complete: {result}")
        return result

    def execute_discussion(self) -> dict[str, Any]:
        """Execute discussion tokens workflow."""
        logger.info("Starting Followin discussion tokens workflow")

        storage_key = "FollowinSourceDiscussion"
        if not self.storage.can_execute_source(
            storage_key, self.source.config.daily_max_executions
        ):
            console.print(
                "[yellow]⚠️ Daily limit reached for Followin discussion[/yellow]"
            )
            return {**self._empty_stats(), "error": "daily limit reached"}

        console.print("[blue]Fetching Followin discussion tokens...[/blue]")
        items = self.source.fetch_discussion_tokens()
        console.print(f"✓ Fetched {len(items)} discussion tokens")

        result = self._publish_items(items, storage_key, "Discussion Tokens")
        self._print_summary(result, "Discussion Tokens")
        logger.info(f"Followin discussion workflow complete: {result}")
        return result

    def _empty_stats(self) -> dict[str, Any]:
        return {
            "items_fetched": 0,
            "items_generated": [],
            "dry_run": self.dry_run,
        }

    def _base_stats(self, items: list[TweetSourceItem]) -> dict[str, Any]:
        return {
            "items_fetched": len(items),
            "items_generated": items,
            "dry_run": self.dry_run,
        }

    def _publish_items(
        self,
        items: list[Any],
        storage_key: str,
        category_name: str,
    ) -> dict[str, Any]:
        """Map Followin items and publish them through the account item publisher."""
        if not items:
            console.print("[yellow]No items found[/yellow]")
            return self._empty_stats()

        # Filter out already published items (BEFORE limit application)
        filtered_items = [
            item
            for item in items
            if not self.storage.is_content_published_today(
                "FollowinSource",
                self._content_type_for_item(storage_key, item),
                str(item.id),
            )
        ]
        filtered_count = len(items) - len(filtered_items)
        console.print(f"✓ Filtered out {filtered_count} already published items")
        logger.info(f"Filtered out {filtered_count} already published items")

        if self.limit and len(filtered_items) > self.limit:
            filtered_items = filtered_items[: self.limit]
            console.print(f"ℹ️ Limited to {self.limit} items")

        mapped_items = [
            self._map_item(item, self._content_type_for_item(storage_key, item))
            for item in filtered_items
        ]
        stats = self._base_stats(mapped_items)
        api_keys = self.target.config.api_keys
        if not self.dry_run and not api_keys:
            logger.warning("No Binance API keys configured; skipping publish")
            return stats

        publish_stats = self.publisher.publish_items(
            mapped_items,
            self.target,
            api_keys,
            self.storage,
            dry_run=self.dry_run,
        )
        stats.update(publish_stats)

        if not self.dry_run:
            self.storage.increment_daily_execution(storage_key)

        return stats

    def _map_item(self, item: Any, content_type: str) -> TweetSourceItem:
        mapped_item = followin_item_to_item(item)
        return mapped_item.model_copy(update={"content_type": content_type})

    def _content_type_for_item(self, storage_key: str, item: Any) -> str:
        storage_content_type = self._content_type_for_storage_key(storage_key)
        if storage_content_type != "unknown":
            return storage_content_type

        if isinstance(item, FollowinTopic):
            return "topics"
        if isinstance(item, FollowinToken):
            if item.category == "discussion":
                return "discussion"
            if item.category == "io_flow":
                return "io_flow"

        return "unknown"

    def _content_type_for_storage_key(self, storage_key: str) -> str:
        content_type_map = {
            "FollowinSourceTopics": "topics",
            "FollowinSourceIOFlow": "io_flow",
            "FollowinSourceDiscussion": "discussion",
        }
        return content_type_map.get(storage_key, "unknown")

    def _print_summary(self, stats: dict[str, Any], category_name: str) -> None:
        table = Table(title=f"Followin {category_name} Execution Summary")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="magenta")
        table.add_row("Items Fetched", str(stats["items_fetched"]))
        table.add_row("Items Generated", str(len(stats["items_generated"])))
        table.add_row("Generated Successfully", str(stats.get("generated_success", 0)))
        table.add_row("Published Successfully", str(stats.get("published_success", 0)))
        table.add_row("Publish Failed", str(stats.get("published_failed", 0)))
        console.print(table)
