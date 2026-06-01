from typing import Any, Dict

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
from binance_square_bot.services.storage import StorageService
from binance_square_bot.services.source.fn_source import FnSource
from binance_square_bot.services.target.binance_target import BinanceTarget

console = Console()


class FnCliService:
    """CLI business logic for Fn news workflow."""

    def __init__(self, dry_run: bool = False, limit: int = None):
        self.dry_run = dry_run
        self.limit = limit
        self.storage = StorageService()
        self.source = FnSource()
        self.target = BinanceTarget()
        self.publisher = AccountItemPublisher()

    def execute(self) -> Dict[str, Any]:
        """Execute the full crawl-generate-publish workflow.

        Returns:
            Dictionary with execution statistics
        """
        logger.info("Starting Fn news workflow")

        # Check execution limit
        if not self.storage.can_execute_source("FnSource", self.source.config.daily_max_executions):
            console.print("[yellow]⚠️ Daily execution limit reached for FnSource[/yellow]")
            return {"error": "daily limit reached"}

        # Fetch articles
        console.print("[blue]📥 Fetching Fn news...[/blue]")
        articles = self.source.fetch()
        console.print(f"✓ Fetched {len(articles)} articles")

        if not articles:
            console.print("[yellow]No articles found[/yellow]")
            return self._empty_stats()

        # 过滤掉当天已发布的
        filtered_items = [
            item for item in articles
            if not self.storage.is_content_published_today("FnSource", "news", item.url)
        ]
        console.print(f"ℹ️ Filtered out {len(articles) - len(filtered_items)} already published items")
        logger.info(f"Filtered out {len(articles) - len(filtered_items)} already published items")

        # Apply limit
        if self.limit and len(filtered_items) > self.limit:
            filtered_items = filtered_items[:self.limit]
            console.print(f"ℹ️ Limited to {self.limit} articles")

        items = [fn_article_to_item(item) for item in filtered_items]
        stats = self._base_stats(items)
        result = self._publish_items(items, stats, "FnSource")
        self._print_summary(result, "Articles")
        logger.info(f"Fn news workflow complete: {result}")
        return result

    def execute_calendar(self) -> Dict[str, Any]:
        """Execute the calendar events workflow."""
        logger.info("Starting Fn calendar workflow")

        if not self.storage.can_execute_source("FnSourceCalendar", self.source.config.daily_max_executions):
            console.print("[yellow]⚠️ Daily execution limit reached for FnSourceCalendar[/yellow]")
            return {"error": "daily limit reached"}

        console.print("[blue]📥 Fetching Fn calendar events...[/blue]")
        events = self.source.fetch_calendar(page_size=self.limit or 10)
        console.print(f"✓ Fetched {len(events)} calendar events")

        if not events:
            console.print("[yellow]No calendar events found[/yellow]")
            return self._empty_stats()

        # 过滤掉当天已发布的
        filtered_items = [
            item for item in events
            if not self.storage.is_content_published_today("FnSource", "calendar", item.url)
        ]
        console.print(f"ℹ️ Filtered out {len(events) - len(filtered_items)} already published items")
        logger.info(f"Filtered out {len(events) - len(filtered_items)} already published items")

        if self.limit and len(filtered_items) > self.limit:
            filtered_items = filtered_items[:self.limit]
            console.print(f"ℹ️ Limited to {self.limit} events")

        items = [fn_calendar_to_item(item) for item in filtered_items]
        stats = self._base_stats(items)
        result = self._publish_items(items, stats, "FnSourceCalendar")
        self._print_summary(result, "Events")
        logger.info(f"FnSourceCalendar workflow complete: {result}")
        return result

    def execute_airdrops(self) -> Dict[str, Any]:
        """Execute the airdrop events workflow."""
        logger.info("Starting Fn airdrop workflow")

        if not self.storage.can_execute_source("FnSourceAirdrops", self.source.config.daily_max_executions):
            console.print("[yellow]⚠️ Daily execution limit reached for FnSourceAirdrops[/yellow]")
            return {"error": "daily limit reached"}

        console.print("[blue]📥 Fetching Fn airdrop events...[/blue]")
        events = self.source.fetch_airdrops(page_size=self.limit or 10)
        console.print(f"✓ Fetched {len(events)} airdrop events")

        if not events:
            console.print("[yellow]No airdrop events found[/yellow]")
            return self._empty_stats()

        # 过滤掉当天已发布的
        filtered_items = [
            item for item in events
            if not self.storage.is_content_published_today("FnSource", "airdrop", item.url)
        ]
        console.print(f"ℹ️ Filtered out {len(events) - len(filtered_items)} already published items")
        logger.info(f"Filtered out {len(events) - len(filtered_items)} already published items")

        if self.limit and len(filtered_items) > self.limit:
            filtered_items = filtered_items[:self.limit]
            console.print(f"ℹ️ Limited to {self.limit} events")

        items = [fn_airdrop_to_item(item) for item in filtered_items]
        stats = self._base_stats(items)
        result = self._publish_items(items, stats, "FnSourceAirdrops")
        self._print_summary(result, "Events")
        logger.info(f"FnSourceAirdrops workflow complete: {result}")
        return result

    def execute_fundraising(self) -> Dict[str, Any]:
        """Execute the fundraising (众筹) events workflow."""
        logger.info("Starting Fn fundraising workflow")

        if not self.storage.can_execute_source("FnSourceFundraising", self.source.config.daily_max_executions):
            console.print("[yellow]⚠️ Daily execution limit reached for FnSourceFundraising[/yellow]")
            return {"error": "daily limit reached"}

        console.print("[blue]📥 Fetching Fn fundraising events...[/blue]")
        events = self.source.fetch_fundraising(page_size=self.limit or 10)
        console.print(f"✓ Fetched {len(events)} fundraising events")

        if not events:
            console.print("[yellow]No fundraising events found[/yellow]")
            return self._empty_stats()

        # 过滤掉当天已发布的
        filtered_items = [
            item for item in events
            if not self.storage.is_content_published_today("FnSource", "fundraising", item.url)
        ]
        console.print(f"ℹ️ Filtered out {len(events) - len(filtered_items)} already published items")
        logger.info(f"Filtered out {len(events) - len(filtered_items)} already published items")

        if self.limit and len(filtered_items) > self.limit:
            filtered_items = filtered_items[:self.limit]
            console.print(f"ℹ️ Limited to {self.limit} events")

        items = [fn_fundraising_to_item(item) for item in filtered_items]
        stats = self._base_stats(items)
        result = self._publish_items(items, stats, "FnSourceFundraising")
        self._print_summary(result, "Events")
        logger.info(f"FnSourceFundraising workflow complete: {result}")
        return result

    def _empty_stats(self) -> Dict[str, Any]:
        return {
            "items_fetched": 0,
            "items_generated": [],
            "dry_run": self.dry_run,
        }

    def _base_stats(self, items: list[TweetSourceItem]) -> Dict[str, Any]:
        return {
            "items_fetched": len(items),
            "items_generated": items,
            "dry_run": self.dry_run,
        }

    def _publish_items(
        self,
        items: list[TweetSourceItem],
        stats: Dict[str, Any],
        source_key: str,
    ) -> Dict[str, Any]:
        publish_stats = self.publisher.publish_items(
            items,
            self.target,
            self.target.config.api_keys,
            self.storage,
            dry_run=self.dry_run,
        )
        stats.update(publish_stats)

        if not self.dry_run:
            self.storage.increment_daily_execution(source_key)

        return stats

    def _print_summary(self, stats: Dict[str, Any], fetched_label: str) -> None:
        table = Table(title="Execution Summary")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="magenta")
        table.add_row(f"{fetched_label} Fetched", str(stats["items_fetched"]))
        table.add_row("Items Generated", str(len(stats["items_generated"])))
        table.add_row("Generated Successfully", str(stats.get("generated_success", 0)))
        table.add_row("Published Successfully", str(stats.get("published_success", 0)))
        table.add_row("Publish Failed", str(stats.get("published_failed", 0)))
        console.print(table)
