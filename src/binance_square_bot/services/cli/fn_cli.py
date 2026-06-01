from typing import Any

from loguru import logger
from rich.console import Console
from rich.table import Table

from binance_square_bot.services.account_item_publisher import AccountItemPublisher
from binance_square_bot.services.generation.mappers import (
    fn_airdrop_to_item,
    fn_article_to_item,
    fn_calendar_to_item,
    fn_fundraising_to_item,
)
from binance_square_bot.services.generation.models import TweetSourceItem
from binance_square_bot.services.source.fn_source import FnSource
from binance_square_bot.services.storage import StorageService
from binance_square_bot.services.target.binance_target import BinanceTarget

console = Console()


class FnCliService:
    """CLI business logic for Fn news workflow."""

    def __init__(self, dry_run: bool = False, limit: int | None = None) -> None:
        self.dry_run = dry_run
        self.limit = limit
        self.storage = StorageService()
        self.source = FnSource()  # type: ignore[no-untyped-call]
        self.target = BinanceTarget()  # type: ignore[no-untyped-call]
        self.publisher = AccountItemPublisher()

    def execute(self) -> dict[str, Any]:
        """Execute the full crawl-generate-publish workflow.

        Returns:
            Dictionary with execution statistics
        """
        logger.info("Starting Fn news workflow")
        stats = self._collect_news_items()
        result = self._publish_items(stats["items_generated"], stats, "FnSource")
        self._print_summary(result, "Articles")
        logger.info(f"Fn news workflow complete: {result}")
        return result

    def collect_items(self, workflow_name: str = "execute") -> dict[str, Any]:
        """Collect mapped source items for parallel orchestration without publishing."""
        collectors = {
            "execute": self._collect_news_items,
            "execute_calendar": self._collect_calendar_items,
            "execute_airdrops": self._collect_airdrop_items,
            "execute_fundraising": self._collect_fundraising_items,
        }
        collector = collectors[workflow_name]
        return collector()

    def _collect_news_items(self) -> dict[str, Any]:
        if not self.storage.can_execute_source(
            "FnSource", self.source.config.daily_max_executions
        ):
            console.print(
                "[yellow]⚠️ Daily execution limit reached for FnSource[/yellow]"
            )
            return {**self._empty_stats(), "error": "daily limit reached"}

        console.print("[blue]📥 Fetching Fn news...[/blue]")
        articles = self.source.fetch()
        console.print(f"✓ Fetched {len(articles)} articles")

        if not articles:
            console.print("[yellow]No articles found[/yellow]")
            return self._empty_stats()

        filtered_items = [
            item
            for item in articles
            if not self.storage.is_content_published_today("FnSource", "news", item.url)
        ]
        filtered_count = len(articles) - len(filtered_items)
        console.print(f"ℹ️ Filtered out {filtered_count} already published items")
        logger.info(f"Filtered out {filtered_count} already published items")

        if self.limit and len(filtered_items) > self.limit:
            filtered_items = filtered_items[: self.limit]
            console.print(f"ℹ️ Limited to {self.limit} articles")

        return self._base_stats([fn_article_to_item(item) for item in filtered_items])

    def execute_calendar(self) -> dict[str, Any]:
        """Execute the calendar events workflow."""
        logger.info("Starting Fn calendar workflow")

        stats = self._collect_calendar_items()
        result = self._publish_items(
            stats["items_generated"], stats, "FnSourceCalendar"
        )
        self._print_summary(result, "Events")
        logger.info(f"FnSourceCalendar workflow complete: {result}")
        return result

    def _collect_calendar_items(self) -> dict[str, Any]:
        if not self.storage.can_execute_source(
            "FnSourceCalendar", self.source.config.daily_max_executions
        ):
            console.print(
                "[yellow]⚠️ Daily execution limit reached for FnSourceCalendar[/yellow]"
            )
            return {**self._empty_stats(), "error": "daily limit reached"}

        console.print("[blue]📥 Fetching Fn calendar events...[/blue]")
        events = self.source.fetch_calendar(page_size=self.limit or 10)
        console.print(f"✓ Fetched {len(events)} calendar events")

        if not events:
            console.print("[yellow]No calendar events found[/yellow]")
            return self._empty_stats()

        filtered_items = [
            item
            for item in events
            if not self.storage.is_content_published_today(
                "FnSource", "calendar", item.url
            )
        ]
        filtered_count = len(events) - len(filtered_items)
        console.print(f"ℹ️ Filtered out {filtered_count} already published items")
        logger.info(f"Filtered out {filtered_count} already published items")

        if self.limit and len(filtered_items) > self.limit:
            filtered_items = filtered_items[: self.limit]
            console.print(f"ℹ️ Limited to {self.limit} events")

        return self._base_stats([fn_calendar_to_item(item) for item in filtered_items])

    def execute_airdrops(self) -> dict[str, Any]:
        """Execute the airdrop events workflow."""
        logger.info("Starting Fn airdrop workflow")

        stats = self._collect_airdrop_items()
        result = self._publish_items(
            stats["items_generated"], stats, "FnSourceAirdrops"
        )
        self._print_summary(result, "Events")
        logger.info(f"FnSourceAirdrops workflow complete: {result}")
        return result

    def _collect_airdrop_items(self) -> dict[str, Any]:
        if not self.storage.can_execute_source(
            "FnSourceAirdrops", self.source.config.daily_max_executions
        ):
            console.print(
                "[yellow]⚠️ Daily execution limit reached for FnSourceAirdrops[/yellow]"
            )
            return {**self._empty_stats(), "error": "daily limit reached"}

        console.print("[blue]📥 Fetching Fn airdrop events...[/blue]")
        events = self.source.fetch_airdrops(page_size=self.limit or 10)
        console.print(f"✓ Fetched {len(events)} airdrop events")

        if not events:
            console.print("[yellow]No airdrop events found[/yellow]")
            return self._empty_stats()

        filtered_items = [
            item
            for item in events
            if not self.storage.is_content_published_today(
                "FnSource", "airdrop", item.url
            )
        ]
        filtered_count = len(events) - len(filtered_items)
        console.print(f"ℹ️ Filtered out {filtered_count} already published items")
        logger.info(f"Filtered out {filtered_count} already published items")

        if self.limit and len(filtered_items) > self.limit:
            filtered_items = filtered_items[: self.limit]
            console.print(f"ℹ️ Limited to {self.limit} events")

        return self._base_stats([fn_airdrop_to_item(item) for item in filtered_items])

    def execute_fundraising(self) -> dict[str, Any]:
        """Execute the fundraising (众筹) events workflow."""
        logger.info("Starting Fn fundraising workflow")

        stats = self._collect_fundraising_items()
        result = self._publish_items(
            stats["items_generated"], stats, "FnSourceFundraising"
        )
        self._print_summary(result, "Events")
        logger.info(f"FnSourceFundraising workflow complete: {result}")
        return result

    def _collect_fundraising_items(self) -> dict[str, Any]:
        if not self.storage.can_execute_source(
            "FnSourceFundraising", self.source.config.daily_max_executions
        ):
            message = "Daily execution limit reached for FnSourceFundraising"
            console.print(f"[yellow]⚠️ {message}[/yellow]")
            return {**self._empty_stats(), "error": "daily limit reached"}

        console.print("[blue]📥 Fetching Fn fundraising events...[/blue]")
        events = self.source.fetch_fundraising(page_size=self.limit or 10)
        console.print(f"✓ Fetched {len(events)} fundraising events")

        if not events:
            console.print("[yellow]No fundraising events found[/yellow]")
            return self._empty_stats()

        filtered_items = [
            item
            for item in events
            if not self.storage.is_content_published_today(
                "FnSource", "fundraising", item.url
            )
        ]
        filtered_count = len(events) - len(filtered_items)
        console.print(f"ℹ️ Filtered out {filtered_count} already published items")
        logger.info(f"Filtered out {filtered_count} already published items")

        if self.limit and len(filtered_items) > self.limit:
            filtered_items = filtered_items[: self.limit]
            console.print(f"ℹ️ Limited to {self.limit} events")

        return self._base_stats(
            [fn_fundraising_to_item(item) for item in filtered_items]
        )

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
        items: list[TweetSourceItem],
        stats: dict[str, Any],
        source_key: str,
    ) -> dict[str, Any]:
        if not items:
            return stats

        api_keys = self.target.config.api_keys
        if not self.dry_run and not api_keys:
            logger.warning("No Binance API keys configured; skipping publish")
            return stats

        publish_stats = self.publisher.publish_items(
            items,
            self.target,
            api_keys,
            self.storage,
            dry_run=self.dry_run,
        )
        stats.update(publish_stats)

        if not self.dry_run:
            self.storage.increment_daily_execution(source_key)

        return stats

    def _print_summary(self, stats: dict[str, Any], fetched_label: str) -> None:
        table = Table(title="Execution Summary")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="magenta")
        table.add_row(f"{fetched_label} Fetched", str(stats["items_fetched"]))
        table.add_row("Items Generated", str(len(stats["items_generated"])))
        table.add_row("Generated Successfully", str(stats.get("generated_success", 0)))
        table.add_row("Published Successfully", str(stats.get("published_success", 0)))
        table.add_row("Publish Failed", str(stats.get("published_failed", 0)))
        console.print(table)
