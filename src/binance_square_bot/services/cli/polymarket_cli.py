# src/binance_square_bot/services/cli/polymarket_cli.py
import time
from typing import Dict, Any
from loguru import logger
from rich.console import Console
from rich.table import Table

from binance_square_bot.services.storage import StorageService
from binance_square_bot.services.source.polymarket_source import PolymarketSource
from binance_square_bot.services.target.binance_target import BinanceTarget

console = Console()


class PolymarketCliService:
    """CLI business logic for Polymarket research workflow."""
    
    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.storage = StorageService()
        self.source = PolymarketSource()
        self.target = BinanceTarget()
    
    def execute(self) -> Dict[str, Any]:
        """Execute the full fetch-generate-publish workflow for Polymarket research."""
        logger.info("Starting Polymarket research workflow")
        
        # Check execution limit
        if not self.storage.can_execute_source(
            "PolymarketSource",
            self.source.config.daily_max_executions
        ):
            console.print("[yellow]⚠️ Daily execution limit reached for PolymarketSource[/yellow]")
            return {"error": "daily limit reached"}
        
        # Fetch markets
        console.print("[blue]🔍 Fetching Polymarket markets...[/blue]")
        markets = self.source.fetch()
        console.print(f"✓ Fetched {len(markets)} markets")
        
        # Generate research tweets
        console.print("[blue]✍️ Generating research tweets...[/blue]")
        tweets = self.source.generate(markets)
        
        stats = {
            "markets_fetched": len(markets),
            "tweets_generated": len(tweets),
            "published_success": 0,
            "published_failed": 0,
            "dry_run": self.dry_run,
        }
        
        if not tweets:
            console.print("[yellow]No suitable markets found for research[/yellow]")
            return stats
        
        if self.dry_run:
            console.print(f"[yellow]🏁 Dry run complete. Generated {len(tweets)} research tweets.[/yellow]")
            for i, tweet in enumerate(tweets, 1):
                console.print(f"\n--- Research Tweet {i} ---")
                console.print(tweet)
            return stats
        
        # Publish to all enabled API keys
        api_keys = self.target.config.api_keys
        if not api_keys:
            console.print("[red]❌ No API keys configured[/red]")
            return stats

        console.print(f"[blue]📤 Publishing to {len(api_keys)} API keys...[/blue]")

        for api_key in api_keys:
            if not self.storage.can_publish_key(
                "BinanceTarget",
                api_key,
                self.target.config.daily_max_posts_per_key
            ):
                from binance_square_bot.models.daily_publish_stats import DailyPublishStatsModel
                key_mask = DailyPublishStatsModel.mask_key(api_key)
                console.print(f"[yellow]⚠️ Daily limit reached for key {key_mask}, skipping[/yellow]")
                continue
            
            for tweet in tweets:
                filtered_tweet = self.target.filter(tweet)
                success, error = self.target.publish(filtered_tweet, api_key)
                
                if success:
                    stats["published_success"] += 1
                    self.storage.increment_daily_publish_count("BinanceTarget", api_key)
                    console.print("[green]✅ Published successfully[/green]")
                else:
                    stats["published_failed"] += 1
                    console.print(f"[red]❌ Publish failed: {error}[/red]")
                
                time.sleep(1.0)
        
        # Increment execution count
        self.storage.increment_daily_execution("PolymarketSource")
        
        # Print summary
        table = Table(title="Polymarket Research Summary")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="magenta")
        table.add_row("Markets Fetched", str(stats["markets_fetched"]))
        table.add_row("Tweets Generated", str(stats["tweets_generated"]))
        table.add_row("Published Successfully", str(stats["published_success"]))
        table.add_row("Publish Failed", str(stats["published_failed"]))
        console.print(table)
        
        logger.info(f"Polymarket research workflow complete: {stats}")
        return stats
    
    def scan(self, top_n: int = 5) -> Dict[str, Any]:
        """Scan markets and show top candidates without generating/publishing."""
        console.print("[blue]🔍 Scanning Polymarket markets...[/blue]")
        markets = self.source.fetch()
        
        # Filter by minimum volume
        min_volume = PolymarketSource.Config.model_fields['min_volume_threshold'].default
        candidates = [m for m in markets if m.volume >= min_volume]
        candidates.sort(key=lambda m: m.volume, reverse=True)
        
        console.print(f"\n[bold cyan]Top {min(top_n, len(candidates))} candidate markets:[/bold cyan]\n")
        for i, market in enumerate(candidates[:top_n], 1):
            console.print(f"[bold]{i}. {market.question}[/]")
            console.print(f"   condition_id: {market.condition_id}")
            console.print(f"   YES: {market.yes_price:.1%}, NO: {market.no_price:.1%}")
            console.print(f"   Volume: ${market.volume:,.0f}")
            console.print("")
        
        console.print(f"Total candidate markets: {len(candidates)} / {len(markets)}")
        return {"total_markets": len(markets), "candidates": len(candidates)}
