import time
from typing import Dict, Any, List, Callable, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from loguru import logger
from rich.console import Console
from rich.table import Table


console = Console()


@dataclass
class TaskResult:
    """Result of a single task."""
    task_name: str
    success: bool
    data: Dict[str, Any]
    error: Optional[str] = None


class ConcurrentExecutor:
    """Execute multiple tasks concurrently.

    Supports:
    - Multiple sources running concurrently
    - Multiple targets running concurrently
    - Multiple API keys running concurrently
    """

    def __init__(self, max_workers: int = 5):
        self.max_workers = max_workers

    def run_parallel(
        self,
        tasks: List[Callable],
        task_names: Optional[List[str]] = None,
        on_complete: Optional[Callable[[str, Dict[str, Any]], None]] = None,
    ) -> Dict[str, TaskResult]:
        """Run tasks in parallel.

        Args:
            tasks: List of callables to execute
            task_names: Optional list of names for each task
            on_complete: Optional callback called when a task completes

        Returns:
            Dictionary mapping task names to results
        """
        if task_names is None:
            task_names = [f"Task_{i}" for i in range(len(tasks))]

        results: Dict[str, TaskResult] = {}

        console.print(f"[blue]🚀 Starting {len(tasks)} tasks with {self.max_workers} workers[/blue]")

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_task = {
                executor.submit(task): name
                for task, name in zip(tasks, task_names)
            }

            for future in as_completed(future_to_task):
                task_name = future_to_task[future]
                try:
                    result_data = future.result()
                    result = TaskResult(
                        task_name=task_name,
                        success=True,
                        data=result_data if isinstance(result_data, dict) else {"result": result_data},
                    )
                    console.print(f"[green]✅ {task_name} completed successfully[/green]")

                    if on_complete:
                        on_complete(task_name, result.data)

                except Exception as e:
                    logger.exception(f"Task {task_name} failed")
                    result = TaskResult(
                        task_name=task_name,
                        success=False,
                        data={},
                        error=str(e),
                    )
                    console.print(f"[red]❌ {task_name} failed: {e}[/red]")

                results[task_name] = result

        # Print summary
        self._print_summary(results)
        return results

    def _print_summary(self, results: Dict[str, TaskResult]) -> None:
        """Print execution summary."""
        success_count = sum(1 for r in results.values() if r.success)
        failed_count = len(results) - success_count

        table = Table(title="Parallel Execution Summary")
        table.add_column("Task", style="cyan")
        table.add_column("Status", style="magenta")
        table.add_column("Detail", style="green")

        for name, result in results.items():
            status = "✅ Success" if result.success else "❌ Failed"
            detail = self._format_result_detail(result.data)
            table.add_row(name, status, detail)

        console.print(table)

        console.print(f"\n[green]✅ {success_count} succeeded[/green], [red]❌ {failed_count} failed[/red]")

    def _format_result_detail(self, data: Dict[str, Any]) -> str:
        """Format result data for display."""
        parts = []
        if "items_fetched" in data:
            parts.append(f"items: {data['items_fetched']}")
        if "tweets_generated" in data:
            parts.append(f"tweets: {data['tweets_generated']}")
        if "published_success" in data:
            parts.append(f"published: {data['published_success']}")
        if "published_failed" in data and data["published_failed"] > 0:
            parts.append(f"failed: {data['published_failed']}")
        if not parts and "result" in data:
            parts.append(str(data["result"])[:30])

        return ", ".join(parts) if parts else "completed"


class SourceParallelPublisher:
    """Publish tweets to multiple targets and API keys concurrently."""

    def __init__(self, max_workers: int = 3):
        self.max_workers = max_workers

    def publish_to_targets(
        self,
        tweets: List[str],
        targets: List[Any],
        api_keys_map: Dict[str, List[str]],
        storage: Any,
        delay_between_publishes: float = 1.0,
    ) -> Dict[str, Any]:
        """Publish tweets to multiple targets and API keys concurrently.

        Args:
            tweets: List of tweet contents to publish
            targets: List of target instances
            api_keys_map: Dict mapping target class name to list of API keys
            storage: Storage service for rate limiting
            delay_between_publishes: Delay between publishes in same thread

        Returns:
            Aggregated statistics
        """
        total_stats = {
            "total_tweets": len(tweets),
            "total_targets": len(targets),
            "published_success": 0,
            "published_failed": 0,
            "target_results": {},
        }

        # Create publish tasks for each (target, api_key, tweet) combination
        publish_tasks: List[Callable] = []
        task_names: List[str] = []

        for target in targets:
            target_name = target.__class__.__name__
            api_keys = api_keys_map.get(target_name, [])

            if not api_keys:
                console.print(f"[yellow]⚠️ No API keys configured for {target_name}, skipping[/yellow]")
                continue

            target_results = {
                "api_keys_used": 0,
                "published_success": 0,
                "published_failed": 0,
            }

            for api_key in api_keys:
                # Check publish limit for this API key
                if not storage.can_publish_key(
                    target_name,
                    api_key,
                    target.config.daily_max_posts_per_key,
                ):
                    from binance_square_bot.models.daily_publish_stats import DailyPublishStatsModel
                    key_mask = DailyPublishStatsModel.mask_key(api_key)
                    console.print(f"[yellow]⚠️ Daily limit reached for key {key_mask}, skipping[/yellow]")
                    continue

                target_results["api_keys_used"] += 1

                # Create a task that publishes all tweets with this API key
                def create_publish_task(tgt, key, tweet_list):
                    def publish_task():
                        task_stats = {"success": 0, "failed": 0}
                        for tweet in tweet_list:
                            filtered_tweet = tgt.filter(tweet)
                            success, error = tgt.publish(filtered_tweet, key)

                            if success:
                                task_stats["success"] += 1
                                storage.increment_daily_publish_count(
                                    tgt.__class__.__name__,
                                    key,
                                )
                            else:
                                task_stats["failed"] += 1

                            time.sleep(delay_between_publishes)

                        return task_stats

                    return publish_task

                task_name = f"{target_name}_{api_key[:8]}..."
                publish_tasks.append(create_publish_task(target, api_key, tweets))
                task_names.append(task_name)

            total_stats["target_results"][target_name] = target_results

        if not publish_tasks:
            console.print("[yellow]⚠️ No publish tasks to execute[/yellow]")
            return total_stats

        # Execute publish tasks concurrently
        console.print(f"[blue]📤 Starting {len(publish_tasks)} concurrent publish tasks[/blue]")

        executor = ConcurrentExecutor(max_workers=self.max_workers)
        results = executor.run_parallel(publish_tasks, task_names)

        # Aggregate results
        for task_name, result in results.items():
            if result.success:
                total_stats["published_success"] += result.data.get("success", 0)
                total_stats["published_failed"] += result.data.get("failed", 0)

        return total_stats


class SourceOrchestrator:
    """Orchestrate multiple sources running in parallel."""

    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers

    def run_sources(
        self,
        source_configs: List[Dict[str, Any]],
        targets: List[Any],
        api_keys_map: Dict[str, List[str]],
        storage: Any,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """Run multiple sources in parallel, then publish to targets.

        Args:
            source_configs: List of source configs with 'source' instance and 'execute_fn'
            targets: List of target instances
            api_keys_map: Dict mapping target class name to list of API keys
            storage: Storage service
            dry_run: If True, only generate without publishing

        Returns:
            Aggregated results from all sources
        """
        # First execute all sources in parallel to fetch and generate tweets
        source_tasks = []
        source_names = []

        for cfg in source_configs:
            source = cfg["source"]
            execute_fn = cfg.get("execute", "execute")
            limit = cfg.get("limit")

            # Create source execution task
            def create_source_task(src, exec_fn, lim):
                def source_task():
                    service_cls = self._get_service_for_source(src.__class__.__name__)
                    service = service_cls(dry_run=dry_run, limit=lim)
                    exec_method = getattr(service, exec_fn)
                    return exec_method()

                return source_task

            source_tasks.append(create_source_task(source, execute_fn, limit))
            source_names.append(source.__class__.__name__)

        # Execute all sources in parallel
        console.print(f"[blue]🚀 Starting {len(source_tasks)} sources in parallel[/blue]")

        executor = ConcurrentExecutor(max_workers=self.max_workers)
        source_results = executor.run_parallel(source_tasks, source_names)

        total_stats = {
            "sources_executed": len(source_configs),
            "source_results": source_results,
        }

        if dry_run:
            console.print("[yellow]🏁 Dry run complete - no publishing[/yellow]")
            return total_stats

        # Aggregate all generated tweets from all sources
        all_tweets: List[str] = []
        for result in source_results.values():
            if result.success:
                tweets = result.data.get("tweets_generated", [])
                if isinstance(tweets, list):
                    all_tweets.extend(tweets)

        if not all_tweets:
            console.print("[yellow]⚠️ No tweets generated from any source[/yellow]")
            return total_stats

        # Publish to all targets concurrently
        console.print(f"[blue]📤 Publishing {len(all_tweets)} tweets to {len(targets)} targets[/blue]")

        publisher = SourceParallelPublisher(max_workers=self.max_workers)
        publish_results = publisher.publish_to_targets(
            tweets=all_tweets,
            targets=targets,
            api_keys_map=api_keys_map,
            storage=storage,
        )

        total_stats["publish_results"] = publish_results
        return total_stats

    def _get_service_for_source(self, source_name: str) -> Any:
        """Get the CLI service class for a source."""
        from binance_square_bot.services.cli import (
            FnCliService,
            PolymarketCliService,
            FollowinCliService,
        )

        service_map = {
            "FnSource": FnCliService,
            "PolymarketSource": PolymarketCliService,
            "FollowinSource": FollowinCliService,
        }

        return service_map.get(source_name, FnCliService)
