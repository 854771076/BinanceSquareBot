import time
from typing import Dict, Any, List
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
        if not self.storage.can_execute_source("FnSource", self.source.config.daily_max_executions):
            console.print("[yellow]⚠️ Daily execution limit reached for FnSource[/yellow]")
            return {"error": "daily limit reached"}

        # Fetch articles
        console.print("[blue]📥 Fetching Fn news...[/blue]")
        articles = self.source.fetch()
        console.print(f"✓ Fetched {len(articles)} articles")

        if not articles:
            console.print("[yellow]No articles found[/yellow]")
            return {"articles_fetched": 0}

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

        # Generate tweets
        console.print("[blue]✍️ Generating tweets...[/blue]")
        tweet_texts = self.source.generate(filtered_items)

        # Add metadata to tweets
        tweets: List[Dict[str, Any]] = []
        for i, tweet_text in enumerate(tweet_texts):
            if i < len(filtered_items):
                tweets.append({
                    "text": tweet_text,
                    "source_name": "FnSource",
                    "content_type": "news",
                    "identifier": filtered_items[i].url,
                })

        stats = {
            "articles_fetched": len(filtered_items),
            "tweets_generated": tweets,
            "published_success": 0,
            "published_failed": 0,
            "dry_run": self.dry_run,
        }

        if self.dry_run:
            console.print(f"[yellow]🏁 Dry run complete. Generated {len(tweets)} tweets.[/yellow]")
            for i, tweet in enumerate(tweets, 1):
                console.print(f"\n--- Tweet {i} ---")
                console.print(tweet["text"])
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
                tweet_text = tweet["text"] if isinstance(tweet, dict) else tweet
                filtered_tweet = self.target.filter(tweet_text)
                success, error = self.target.publish(filtered_tweet, api_key)

                if success:
                    stats["published_success"] += 1
                    self.storage.increment_daily_publish_count("BinanceTarget", api_key)
                    # Mark content as published (if metadata available)
                    if isinstance(tweet, dict) and "source_name" in tweet:
                        self.storage.mark_content_published(
                            source_name=tweet["source_name"],
                            content_type=tweet.get("content_type", "unknown"),
                            content_identifier=tweet.get("identifier", ""),
                        )
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
        table.add_row("Tweets Generated", str(len(stats["tweets_generated"])))
        table.add_row("Published Successfully", str(stats["published_success"]))
        table.add_row("Publish Failed", str(stats["published_failed"]))
        console.print(table)

        logger.info(f"Fn news workflow complete: {stats}")
        return stats

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
            return {"events_fetched": 0}

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

        console.print("[blue]✍️ Generating tweets...[/blue]")
        tweet_texts = self.source.generate_calendar(filtered_items)

        # Add metadata to tweets
        tweets: List[Dict[str, Any]] = []
        for i, tweet_text in enumerate(tweet_texts):
            if i < len(filtered_items):
                tweets.append({
                    "text": tweet_text,
                    "source_name": "FnSource",
                    "content_type": "calendar",
                    "identifier": filtered_items[i].url,
                })

        stats = {
            "events_fetched": len(filtered_items),
            "tweets_generated": tweets,
            "published_success": 0,
            "published_failed": 0,
            "dry_run": self.dry_run,
        }

        if self.dry_run:
            console.print(f"[yellow]🏁 Dry run complete. Generated {len(tweets)} tweets.[/yellow]")
            for i, tweet in enumerate(tweets, 1):
                console.print(f"\n--- Calendar Tweet {i} ---")
                console.print(tweet["text"])
            return stats

        return self._publish_tweets(tweets, stats, "FnSourceCalendar")

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
            return {"events_fetched": 0}

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

        console.print("[blue]✍️ Generating tweets...[/blue]")
        tweet_texts = self.source.generate_airdrops(filtered_items)

        # Add metadata to tweets
        tweets: List[Dict[str, Any]] = []
        for i, tweet_text in enumerate(tweet_texts):
            if i < len(filtered_items):
                tweets.append({
                    "text": tweet_text,
                    "source_name": "FnSource",
                    "content_type": "airdrop",
                    "identifier": filtered_items[i].url,
                })

        stats = {
            "events_fetched": len(filtered_items),
            "tweets_generated": tweets,
            "published_success": 0,
            "published_failed": 0,
            "dry_run": self.dry_run,
        }

        if self.dry_run:
            console.print(f"[yellow]🏁 Dry run complete. Generated {len(tweets)} tweets.[/yellow]")
            for i, tweet in enumerate(tweets, 1):
                console.print(f"\n--- Airdrop Tweet {i} ---")
                console.print(tweet["text"])
            return stats

        return self._publish_tweets(tweets, stats, "FnSourceAirdrops")

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
            return {"events_fetched": 0}

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

        console.print("[blue]✍️ Generating tweets...[/blue]")
        tweet_texts = self.source.generate_fundraising(filtered_items)

        # Add metadata to tweets
        tweets: List[Dict[str, Any]] = []
        for i, tweet_text in enumerate(tweet_texts):
            if i < len(filtered_items):
                tweets.append({
                    "text": tweet_text,
                    "source_name": "FnSource",
                    "content_type": "fundraising",
                    "identifier": filtered_items[i].url,
                })

        stats = {
            "events_fetched": len(filtered_items),
            "tweets_generated": tweets,
            "published_success": 0,
            "published_failed": 0,
            "dry_run": self.dry_run,
        }

        if self.dry_run:
            console.print(f"[yellow]🏁 Dry run complete. Generated {len(tweets)} tweets.[/yellow]")
            for i, tweet in enumerate(tweets, 1):
                console.print(f"\n--- Fundraising Tweet {i} ---")
                console.print(tweet["text"])
            return stats

        return self._publish_tweets(tweets, stats, "FnSourceFundraising")

    def _publish_tweets(self, tweets: List[Dict[str, Any]], stats: Dict[str, Any], source_key: str) -> Dict[str, Any]:
        """Helper method to publish tweets."""
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
                tweet_text = tweet["text"] if isinstance(tweet, dict) else tweet
                filtered_tweet = self.target.filter(tweet_text)
                success, error = self.target.publish(filtered_tweet, api_key)

                if success:
                    stats["published_success"] += 1
                    self.storage.increment_daily_publish_count("BinanceTarget", api_key)
                    # Mark content as published (if metadata available)
                    if isinstance(tweet, dict) and "source_name" in tweet:
                        self.storage.mark_content_published(
                            source_name=tweet["source_name"],
                            content_type=tweet.get("content_type", "unknown"),
                            content_identifier=tweet.get("identifier", ""),
                        )
                    console.print("[green]✅ Published successfully[/green]")
                else:
                    stats["published_failed"] += 1
                    console.print(f"[red]❌ Publish failed: {error}[/red]")

                time.sleep(1.0)

        self.storage.increment_daily_execution(source_key)

        table = Table(title="Execution Summary")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="magenta")
        table.add_row("Events Fetched", str(stats["events_fetched"]))
        table.add_row("Tweets Generated", str(len(stats["tweets_generated"])))
        table.add_row("Published Successfully", str(stats["published_success"]))
        table.add_row("Publish Failed", str(stats["published_failed"]))
        console.print(table)

        logger.info(f"{source_key} workflow complete: {stats}")
        return stats
