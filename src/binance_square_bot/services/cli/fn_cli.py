import time
from typing import Dict, Any
from loguru import logger
from rich.console import Console
from rich.table import Table

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

    def execute(self) -> Dict[str, Any]:
        """Execute the full crawl-generate-publish workflow.

        Returns:
            Dictionary with execution statistics
        """
        logger.info("Starting Fn news workflow")

        # Check execution limit
        if not self.storage.can_execute_source("FnSource", FnSource.Config.model_fields["daily_max_executions"].default):
            console.print("[yellow]⚠️ Daily execution limit reached for FnSource[/yellow]")
            return {"error": "daily limit reached"}

        # Fetch articles
        console.print("[blue]📥 Fetching Fn news...[/blue]")
        articles = self.source.fetch()
        console.print(f"✓ Fetched {len(articles)} articles")

        if not articles:
            console.print("[yellow]No articles found[/yellow]")
            return {"articles_fetched": 0}

        # Apply limit
        if self.limit and len(articles) > self.limit:
            articles = articles[:self.limit]
            console.print(f"ℹ️ Limited to {self.limit} articles")

        # Generate tweets
        console.print("[blue]✍️ Generating tweets...[/blue]")
        tweets = self.source.generate(articles)

        stats = {
            "articles_fetched": len(articles),
            "tweets_generated": len(tweets),
            "published_success": 0,
            "published_failed": 0,
            "dry_run": self.dry_run,
        }

        if self.dry_run:
            console.print(f"[yellow]🏁 Dry run complete. Generated {len(tweets)} tweets.[/yellow]")
            for i, tweet in enumerate(tweets, 1):
                console.print(f"\n--- Tweet {i} ---")
                console.print(tweet)
            return stats

        # Publish to all enabled API keys
        api_keys = BinanceTarget.Config.model_fields["api_keys"].default
        if not api_keys:
            console.print("[red]❌ No API keys configured[/red]")
            return stats

        console.print(f"[blue]📤 Publishing to {len(api_keys)} API keys...[/blue]")

        for api_key in api_keys:
            # Check per-key publish limit
            if not self.storage.can_publish_key(
                "BinanceTarget",
                api_key,
                BinanceTarget.Config.model_fields["daily_max_posts_per_key"].default
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

                # Add delay between publishes
                time.sleep(1.0)

        # Increment execution count after successful run
        self.storage.increment_daily_execution("FnSource")

        # Print summary
        table = Table(title="Execution Summary")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="magenta")
        table.add_row("Articles Fetched", str(stats["articles_fetched"]))
        table.add_row("Tweets Generated", str(stats["tweets_generated"]))
        table.add_row("Published Successfully", str(stats["published_success"]))
        table.add_row("Publish Failed", str(stats["published_failed"]))
        console.print(table)

        logger.info(f"Fn news workflow complete: {stats}")
        return stats
