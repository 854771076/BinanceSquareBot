import time
from typing import Dict, Any, List
from loguru import logger
from rich.console import Console
from rich.table import Table

from binance_square_bot.services.storage import StorageService
from binance_square_bot.services.source.followin_source import FollowinSource
from binance_square_bot.services.target.binance_target import BinanceTarget

console = Console()


class FollowinCliService:
    """CLI business logic for Followin workflow."""

    def __init__(self, dry_run: bool = False, limit: int = None):
        self.dry_run = dry_run
        self.limit = limit
        self.storage = StorageService()
        self.source = FollowinSource()
        self.target = BinanceTarget()

    def execute(self) -> Dict[str, Any]:
        """Execute the full crawl-generate-publish workflow.

        Returns:
            Dictionary with execution statistics
        """
        logger.info("Starting Followin workflow")

        # Check execution limit
        if not self.storage.can_execute_source("FollowinSource", self.source.config.daily_max_executions):
            console.print("[yellow]⚠️ Daily execution limit reached for FollowinSource[/yellow]")
            return {"error": "daily limit reached"}

        # Fetch items
        console.print("[blue]Fetching Followin data...[/blue]")
        items = self.source.fetch()
        console.print(f"✓ Fetched {len(items)} items (topics + tokens)")

        if not items:
            console.print("[yellow]No items found[/yellow]")
            return {"items_fetched": 0}

        # Apply limit
        if self.limit and len(items) > self.limit:
            items = items[:self.limit]
            console.print(f"ℹ️ Limited to {self.limit} items")

        # Generate tweets
        console.print("[blue]✍️ Generating tweets...[/blue]")
        tweets = self.source.generate(items)

        stats = {
            "items_fetched": len(items),
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
        api_keys = self.target.config.api_keys
        if not api_keys:
            console.print("[red]❌ No API keys configured[/red]")
            return stats

        console.print(f"[blue]📤 Publishing to {len(api_keys)} API keys...[/blue]")

        for api_key in api_keys:
            # Check per-key publish limit
            if not self.storage.can_publish_key(
                "BinanceTarget",
                api_key,
                self.target.config.daily_max_posts_per_key
            ):
                from binance_square_bot.services.target.binance_target import mask_api_key
                key_mask = mask_api_key(api_key)
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
        self.storage.increment_daily_execution("FollowinSource")

        # Print summary
        table = Table(title="Followin Execution Summary")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="magenta")
        table.add_row("Items Fetched", str(stats["items_fetched"]))
        table.add_row("Tweets Generated", str(stats["tweets_generated"]))
        table.add_row("Published Successfully", str(stats["published_success"]))
        table.add_row("Publish Failed", str(stats["published_failed"]))
        console.print(table)

        logger.info(f"Followin workflow complete: {stats}")
        return stats

    def execute_topics(self) -> Dict[str, Any]:
        """Execute trending topics workflow."""
        logger.info("Starting Followin trending topics workflow")

        storage_key = "FollowinSourceTopics"
        if not self.storage.can_execute_source(storage_key, self.source.config.daily_max_executions):
            console.print("[yellow]⚠️ Daily limit reached for Followin trending topics[/yellow]")
            return {"error": "daily limit reached"}

        console.print("[blue]Fetching Followin trending topics...[/blue]")
        items = self.source.fetch_trending_topics()
        console.print(f"✓ Fetched {len(items)} trending topics")

        return self._publish_items(items, storage_key, "Trending Topics")

    def execute_io_flow(self) -> Dict[str, Any]:
        """Execute IO flow tokens workflow."""
        logger.info("Starting Followin IO flow tokens workflow")

        storage_key = "FollowinSourceIOFlow"
        if not self.storage.can_execute_source(storage_key, self.source.config.daily_max_executions):
            console.print("[yellow]⚠️ Daily limit reached for Followin IO flow[/yellow]")
            return {"error": "daily limit reached"}

        console.print("[blue]Fetching Followin IO flow tokens...[/blue]")
        items = self.source.fetch_io_flow_tokens()
        console.print(f"✓ Fetched {len(items)} IO flow tokens")

        return self._publish_items(items, storage_key, "IO Flow Tokens")

    def execute_discussion(self) -> Dict[str, Any]:
        """Execute discussion tokens workflow."""
        logger.info("Starting Followin discussion tokens workflow")

        storage_key = "FollowinSourceDiscussion"
        if not self.storage.can_execute_source(storage_key, self.source.config.daily_max_executions):
            console.print("[yellow]⚠️ Daily limit reached for Followin discussion[/yellow]")
            return {"error": "daily limit reached"}

        console.print("[blue]Fetching Followin discussion tokens...[/blue]")
        items = self.source.fetch_discussion_tokens()
        console.print(f"✓ Fetched {len(items)} discussion tokens")

        return self._publish_items(items, storage_key, "Discussion Tokens")

    def _publish_items(self, items: List, storage_key: str, category_name: str) -> Dict[str, Any]:
        """Helper method to fetch, generate and publish items."""
        if not items:
            console.print("[yellow]No items found[/yellow]")
            return {"items_fetched": 0}

        # Determine content_type based on storage_key
        content_type_map = {
            "FollowinSourceTopics": "topics",
            "FollowinSourceIOFlow": "io_flow",
            "FollowinSourceDiscussion": "discussion",
        }
        content_type = content_type_map.get(storage_key, "unknown")

        # Filter out already published items (BEFORE limit application)
        filtered_items = [
            item for item in items
            if not self.storage.is_content_published_today("FollowinSource", content_type, str(item.id))
        ]
        console.print(f"✓ Filtered out {len(items) - len(filtered_items)} already published items")
        logger.info(f"Filtered out {len(items) - len(filtered_items)} already published items")

        items = filtered_items

        if self.limit and len(items) > self.limit:
            items = items[:self.limit]
            console.print(f"ℹ️ Limited to {self.limit} items")

        console.print("[blue]✍️ Generating tweets...[/blue]")
        tweets = self.source.generate(items)

        stats = {
            "items_fetched": len(items),
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
                from binance_square_bot.services.target.binance_target import mask_api_key
                key_mask = mask_api_key(api_key)
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

        self.storage.increment_daily_execution(storage_key)

        table = Table(title=f"Followin {category_name} Execution Summary")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="magenta")
        table.add_row("Items Fetched", str(stats["items_fetched"]))
        table.add_row("Tweets Generated", str(stats["tweets_generated"]))
        table.add_row("Published Successfully", str(stats["published_success"]))
        table.add_row("Publish Failed", str(stats["published_failed"]))
        console.print(table)

        logger.info(f"Followin {category_name} workflow complete: {stats}")
        return stats
