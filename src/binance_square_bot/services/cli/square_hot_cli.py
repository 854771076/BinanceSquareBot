from typing import Any

from loguru import logger
from rich.console import Console
from rich.table import Table

from binance_square_bot.services.account_item_publisher import AccountItemPublisher
from binance_square_bot.services.source.square_hot_source import SquareHotSource
from binance_square_bot.services.storage import StorageService
from binance_square_bot.services.target.binance_target import BinanceTarget

console = Console()


class SquareHotCliService:
    """CLI workflow: crawl Binance Square hot posts, rewrite, republish."""

    SOURCE_NAME = "SquareHotSource"

    def __init__(self, dry_run: bool = False, limit: int | None = None) -> None:
        self.dry_run = dry_run
        self.limit = limit
        self.storage = StorageService()
        self.source = SquareHotSource()  # type: ignore[no-untyped-call]
        self.target = BinanceTarget()  # type: ignore[no-untyped-call]
        self.publisher = AccountItemPublisher()

    def execute(self) -> dict[str, Any]:
        logger.info("Starting SquareHot workflow")
        if not self.source.config.enabled:
            console.print(
                "[yellow]SquareHotSource is disabled "
                "(set SQUARE_HOT_SOURCE_ENABLED=true).[/yellow]"
            )
            return self._empty_stats()
        if not self.storage.can_execute_source(
            self.SOURCE_NAME, self.source.config.daily_max_executions
        ):
            console.print("[yellow]⚠️ Daily limit reached for SquareHotSource[/yellow]")
            return {**self._empty_stats(), "error": "daily limit reached"}

        console.print("[blue]📥 Fetching Binance Square hot posts...[/blue]")
        items = self.source.fetch()
        console.print(f"✓ Prepared {len(items)} rewrite items")

        items = [
            it
            for it in items
            if not self.storage.is_content_published_today(
                self.SOURCE_NAME, it.content_type, it.identifier
            )
        ]
        if self.limit:
            items = items[: self.limit]

        result = self._publish(items)
        if not self.dry_run:
            self.storage.increment_daily_execution(self.SOURCE_NAME)
        self._print_summary(result)
        return result

    def collect_items(self, workflow_name: str = "execute") -> dict[str, Any]:
        items = self.source.fetch()
        items = [
            it
            for it in items
            if not self.storage.is_content_published_today(
                self.SOURCE_NAME, it.content_type, it.identifier
            )
        ]
        if self.limit:
            items = items[: self.limit]
        return {"items_fetched": len(items), "items_generated": items, "dry_run": self.dry_run}

    def _publish(self, items: list) -> dict[str, Any]:
        stats: dict[str, Any] = {
            "items_fetched": len(items),
            "items_generated": items,
            "dry_run": self.dry_run,
        }
        if not items:
            return stats
        api_keys = self.target.config.api_keys
        if not self.dry_run and not api_keys:
            logger.warning("No Binance API keys configured; skipping publish")
            return stats
        publish_stats = self.publisher.publish_items(
            items, self.target, api_keys, self.storage, dry_run=self.dry_run
        )
        stats.update(publish_stats)
        return stats

    def _empty_stats(self) -> dict[str, Any]:
        return {"items_fetched": 0, "items_generated": [], "dry_run": self.dry_run}

    def _print_summary(self, stats: dict[str, Any]) -> None:
        table = Table(title="SquareHot Workflow Summary")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="magenta")
        table.add_row("Items", str(stats.get("items_fetched", 0)))
        table.add_row("Generated Successfully", str(stats.get("generated_success", 0)))
        table.add_row("Published Successfully", str(stats.get("published_success", 0)))
        table.add_row("Publish Failed", str(stats.get("published_failed", 0)))
        console.print(table)
