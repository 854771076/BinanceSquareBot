# src/binance_square_bot/services/cli/polymarket_cli.py
from typing import Any

from loguru import logger
from rich.console import Console
from rich.table import Table

from binance_square_bot.services.account_item_publisher import AccountItemPublisher
from binance_square_bot.services.generation.mappers import polymarket_to_item
from binance_square_bot.services.generation.models import TweetSourceItem
from binance_square_bot.services.source.polymarket_source import (
    PolymarketMarket,
    PolymarketSource,
)
from binance_square_bot.services.storage import StorageService
from binance_square_bot.services.target.binance_target import BinanceTarget

console = Console()


class PolymarketCliService:
    """CLI business logic for Polymarket research workflow."""

    def __init__(self, dry_run: bool = False, limit: int | None = None) -> None:
        self.dry_run = dry_run
        self.limit = limit
        self.storage = StorageService()
        self.source = PolymarketSource()  # type: ignore[no-untyped-call]
        self.target = BinanceTarget()  # type: ignore[no-untyped-call]
        self.publisher = AccountItemPublisher()

    def execute(self) -> dict[str, Any]:
        """Execute the full fetch-generate-publish workflow for Polymarket research."""
        logger.info("Starting Polymarket research workflow")

        # Check execution limit
        if not self.storage.can_execute_source(
            "PolymarketSource", self.source.config.daily_max_executions
        ):
            console.print(
                "[yellow]⚠️ Daily execution limit reached for PolymarketSource[/yellow]"
            )
            return {**self._empty_stats(), "error": "daily limit reached"}

        stats = self.collect_items()
        items = stats["items_generated"]

        if not items:
            console.print("[yellow]No suitable markets found for research[/yellow]")
            return stats

        api_keys = self.target.config.api_keys
        if not self.dry_run and not api_keys:
            console.print("[red]❌ No API keys configured[/red]")
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
            self.storage.increment_daily_execution("PolymarketSource")

        # Print summary
        table = Table(title="Polymarket Research Summary")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="magenta")
        table.add_row("Markets Fetched", str(stats["markets_fetched"]))
        table.add_row("Items Generated", str(len(stats["items_generated"])))
        table.add_row("Generated Successfully", str(stats.get("generated_success", 0)))
        table.add_row("Published Successfully", str(stats.get("published_success", 0)))
        table.add_row("Publish Failed", str(stats.get("published_failed", 0)))
        console.print(table)

        logger.info(f"Polymarket research workflow complete: {stats}")
        return stats

    def collect_items(self, workflow_name: str = "execute") -> dict[str, Any]:
        """Collect mapped source items for parallel orchestration without publishing."""
        if workflow_name != "execute":
            raise AttributeError(f"Unknown Polymarket workflow: {workflow_name}")

        console.print("[blue]🔍 Fetching Polymarket markets...[/blue]")
        markets = self.source.fetch()
        console.print(f"✓ Fetched {len(markets)} markets")

        candidates = self._candidate_markets(markets)
        unpublished_candidates = [
            market
            for market in candidates
            if not self.storage.is_content_published_today(
                "PolymarketSource",
                "polymarket_research",
                market.condition_id,
            )
        ]
        items = [polymarket_to_item(market) for market in unpublished_candidates]
        return self._base_stats(len(markets), items)

    def _candidate_markets(
        self, markets: list[PolymarketMarket]
    ) -> list[PolymarketMarket]:
        candidates = [
            market
            for market in markets
            if market.volume >= self.source.config.min_volume_threshold
            and (
                market.yes_price >= self.source.config.min_win_rate
                or market.no_price >= self.source.config.min_win_rate
            )
            and (
                market.yes_price <= self.source.config.max_win_rate
                or market.no_price <= self.source.config.max_win_rate
            )
        ]
        candidates.sort(key=lambda market: market.volume, reverse=True)
        return candidates[:5]

    def _empty_stats(self) -> dict[str, Any]:
        return {
            "markets_fetched": 0,
            "items_fetched": 0,
            "items_generated": [],
            "dry_run": self.dry_run,
        }

    def _base_stats(
        self, markets_fetched: int, items: list[TweetSourceItem]
    ) -> dict[str, Any]:
        return {
            "markets_fetched": markets_fetched,
            "items_fetched": len(items),
            "items_generated": items,
            "dry_run": self.dry_run,
        }

    def scan(self, top_n: int = 5) -> dict[str, Any]:
        """Scan markets and show top candidates without generating/publishing."""
        console.print("[blue]🔍 Scanning Polymarket markets...[/blue]")
        markets = self.source.fetch()

        # Filter by minimum volume
        min_volume = PolymarketSource.Config.model_fields[
            "min_volume_threshold"
        ].default
        candidates = [m for m in markets if m.volume >= min_volume]
        candidates.sort(key=lambda m: m.volume, reverse=True)

        candidate_count = min(top_n, len(candidates))
        console.print(
            f"\n[bold cyan]Top {candidate_count} candidate markets:[/bold cyan]\n"
        )
        for i, market in enumerate(candidates[:top_n], 1):
            console.print(f"[bold]{i}. {market.question}[/]")
            console.print(f"   condition_id: {market.condition_id}")
            console.print(f"   YES: {market.yes_price:.1%}, NO: {market.no_price:.1%}")
            console.print(f"   Volume: ${market.volume:,.0f}")
            console.print("")

        console.print(f"Total candidate markets: {len(candidates)} / {len(markets)}")
        return {"total_markets": len(markets), "candidates": len(candidates)}
