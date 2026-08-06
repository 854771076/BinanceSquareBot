import random
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any, cast

from loguru import logger
from rich.console import Console
from rich.table import Table

from binance_square_bot.services.account_item_publisher import AccountItemPublisher
from binance_square_bot.services.generation.models import TweetSourceItem
from binance_square_bot.services.target.binance_target import mask_api_key

console = Console()


@dataclass
class TaskResult:
    """Result of a single task."""

    task_name: str
    success: bool
    data: dict[str, Any]
    error: str | None = None


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
        tasks: list[Callable[[], Any]],
        task_names: list[str] | None = None,
        on_complete: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> dict[str, TaskResult]:
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

        results: dict[str, TaskResult] = {}

        console.print(
            "[blue]🚀 Starting "
            f"{len(tasks)} tasks with {self.max_workers} workers[/blue]"
        )

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_task = {
                executor.submit(task): name
                for task, name in zip(tasks, task_names, strict=True)
            }

            for future in as_completed(future_to_task):
                task_name = future_to_task[future]
                try:
                    result_data = future.result()
                    result = TaskResult(
                        task_name=task_name,
                        success=True,
                        data=result_data
                        if isinstance(result_data, dict)
                        else {"result": result_data},
                    )
                    console.print(
                        f"[green]✅ {task_name} completed successfully[/green]"
                    )

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

    def _print_summary(self, results: dict[str, TaskResult]) -> None:
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

        console.print(
            f"\n[green]✅ {success_count} succeeded[/green], "
            f"[red]❌ {failed_count} failed[/red]"
        )

    def _format_result_detail(self, data: dict[str, Any]) -> str:
        """Format result data for display."""
        parts = []
        if "items_fetched" in data:
            parts.append(f"items: {data['items_fetched']}")
        if "items_generated" in data:
            items = data["items_generated"]
            count = len(items) if isinstance(items, list) else items
            parts.append(f"items generated: {count}")
        elif "tweets_generated" in data:
            tweets = data["tweets_generated"]
            count = len(tweets) if isinstance(tweets, list) else tweets
            parts.append(f"tweets: {count}")
        if "published_success" in data:
            parts.append(f"published: {data['published_success']}")
        if "published_failed" in data and data["published_failed"] > 0:
            parts.append(f"failed: {data['published_failed']}")
        if not parts and "result" in data:
            parts.append(str(data["result"])[:30])

        return ", ".join(parts) if parts else "completed"


class SourceParallelPublisher:
    """Publish source items to multiple targets through account-level publishers."""

    def __init__(self, max_workers: int = 3):
        self.max_workers = max_workers

    def publish_to_targets(
        self,
        tweets: list[Any],
        targets: list[Any],
        api_keys_map: dict[str, list[str]],
        storage: Any,
        delay_between_publishes: float = 1.0,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Publish content items to every available account for each target.

        The parameter name remains ``tweets`` for backward compatibility, but the
        values are treated as normalized TweetSourceItem content items.
        """
        normalized_items = self._normalize_items(tweets)
        unique_items = self._deduplicate_items(normalized_items)
        self._print_dedupe_summary(len(normalized_items), len(unique_items))

        filtered_items = self._filter_already_published(unique_items, storage)
        self._print_filter_summary(len(unique_items), len(filtered_items))

        total_stats = self._empty_stats(filtered_items, targets)
        if not filtered_items:
            console.print("[yellow]⚠️ No items to publish[/yellow]")
            return total_stats

        publish_tasks, task_names = self._build_publish_tasks(
            targets=targets,
            api_keys_map=api_keys_map,
            storage=storage,
            items=filtered_items,
            delay_between_publishes=delay_between_publishes,
            dry_run=dry_run,
            total_stats=total_stats,
        )

        if not publish_tasks:
            console.print("[yellow]⚠️ No publish tasks to execute[/yellow]")
            return total_stats

        console.print(
            "[blue]📤 Starting "
            f"{len(publish_tasks)} account item publish tasks[/blue]"
        )

        executor = ConcurrentExecutor(max_workers=self.max_workers)
        results = executor.run_parallel(publish_tasks, task_names)
        self._aggregate_publish_results(results, total_stats)
        return total_stats

    def _empty_stats(
        self,
        items: list[Any],
        targets: list[Any],
    ) -> dict[str, Any]:
        return {
            "total_items": len(items),
            "total_tweets": len(items),
            "total_targets": len(targets),
            "generated_success": 0,
            "generated_failed": 0,
            "published_success": 0,
            "published_failed": 0,
            "target_results": {},
        }

    def _build_publish_tasks(
        self,
        *,
        targets: list[Any],
        api_keys_map: dict[str, list[str]],
        storage: Any,
        items: list[Any],
        delay_between_publishes: float,
        dry_run: bool,
        total_stats: dict[str, Any],
    ) -> tuple[list[Callable[[], dict[str, Any]]], list[str]]:
        publish_tasks: list[Callable[[], dict[str, Any]]] = []
        task_names: list[str] = []

        for target in targets:
            target_name = target.__class__.__name__
            api_keys = api_keys_map.get(target_name, [])
            if not api_keys:
                console.print(
                    f"[yellow]⚠️ No API keys for {target_name}, skipping[/yellow]"
                )
                continue

            available_keys = self._available_api_keys(target, api_keys, storage)
            if not available_keys:
                console.print(
                    f"[yellow]⚠️ No available API keys for {target_name}[/yellow]"
                )
                continue

            total_stats["target_results"][target_name] = {
                "api_keys_used": len(available_keys),
                "items_total": len(items),
                "generated_success": 0,
                "generated_failed": 0,
                "published_success": 0,
                "published_failed": 0,
            }
            task_names.append(
                f"{target_name}_({len(items)}items_{len(available_keys)}keys)"
            )
            publish_tasks.append(
                self._create_publish_task(
                    target=target,
                    api_keys=available_keys,
                    items=items,
                    storage=storage,
                    delay_between_publishes=delay_between_publishes,
                    dry_run=dry_run,
                )
            )

        return publish_tasks, task_names

    def _create_publish_task(
        self,
        *,
        target: Any,
        api_keys: list[str],
        items: list[Any],
        storage: Any,
        delay_between_publishes: float,
        dry_run: bool,
    ) -> Callable[[], dict[str, Any]]:
        def publish_task() -> dict[str, Any]:
            publisher = AccountItemPublisher(
                delay_between_publishes=delay_between_publishes
            )
            return cast(
                dict[str, Any],
                publisher.publish_items(
                    items=items,
                    target=target,
                    api_keys=api_keys,
                    storage=storage,
                    dry_run=dry_run,
                ),
            )

        return publish_task

    def _normalize_items(self, items: list[Any]) -> list[TweetSourceItem]:
        normalized_items: list[TweetSourceItem] = []
        skipped_count = 0

        for item in items:
            normalized_item = self._normalize_item(item)
            if normalized_item is None:
                skipped_count += 1
                console.print(
                    "[yellow]⚠️ Skipping unsupported legacy publish item "
                    f"of type {type(item).__name__}[/yellow]"
                )
                logger.warning(
                    "Skipping unsupported legacy publish item of type %s",
                    type(item).__name__,
                )
                continue
            normalized_items.append(normalized_item)

        if skipped_count:
            console.print(
                f"[yellow]⚠️ Skipped {skipped_count} unsupported publish items[/yellow]"
            )
            logger.warning("Skipped %s unsupported publish items", skipped_count)

        return normalized_items

    def _normalize_item(self, item: Any) -> TweetSourceItem | None:
        if isinstance(item, TweetSourceItem):
            return item
        if isinstance(item, dict):
            return self._legacy_dict_to_item(item)
        return None

    def _legacy_dict_to_item(self, item: dict[str, Any]) -> TweetSourceItem | None:
        required_keys = ("source_name", "content_type", "identifier")
        if not all(key in item for key in required_keys):
            return None

        identifier = str(item["identifier"])
        metadata = item.get("metadata")
        return TweetSourceItem(
            source_name=str(item["source_name"]),
            content_type=str(item["content_type"]),
            identifier=identifier,
            title=str(item.get("title") or identifier),
            summary=str(item.get("summary") or item.get("text") or ""),
            url=item.get("url"),
            metadata=metadata if isinstance(metadata, dict) else {},
        )

    def _available_api_keys(
        self,
        target: Any,
        api_keys: list[str],
        storage: Any,
    ) -> list[str]:
        target_name = target.__class__.__name__
        available_keys = []
        for api_key in api_keys:
            if storage.can_publish_key(
                target_name,
                api_key,
                target.config.daily_max_posts_per_key,
            ):
                available_keys.append(api_key)
            else:
                key_mask = mask_api_key(api_key)
                console.print(
                    f"[yellow]⚠️ Daily limit for key {key_mask}, skipping[/yellow]"
                )
        return available_keys

    def _aggregate_publish_results(
        self,
        results: dict[str, TaskResult],
        total_stats: dict[str, Any],
    ) -> None:
        for task_name, result in results.items():
            if not result.success:
                continue

            target_name = task_name.split("_(", 1)[0]
            target_result = total_stats["target_results"].get(target_name)
            for stat_name in (
                "generated_success",
                "generated_failed",
                "published_success",
                "published_failed",
            ):
                stat_value = int(result.data.get(stat_name, 0))
                total_stats[stat_name] += stat_value
                if target_result is not None:
                    target_result[stat_name] += stat_value

    def _deduplicate_items(self, items: list[Any]) -> list[Any]:
        unique_items: list[Any] = []
        seen_identities = set()
        for item in items:
            identity = self._item_identity(item)
            if identity is None or identity not in seen_identities:
                if identity is not None:
                    seen_identities.add(identity)
                unique_items.append(item)
        return unique_items

    def _filter_already_published(
        self,
        items: list[Any],
        storage: Any,
    ) -> list[Any]:
        filtered_items: list[Any] = []
        for item in items:
            identity = self._item_identity(item)
            if identity is None:
                filtered_items.append(item)
                continue

            source_name, content_type, identifier = identity
            if storage.is_content_published_today(
                source_name,
                content_type,
                identifier,
            ):
                console.print(
                    f"[yellow]⏭️ Already published: {identifier[:50]}...[/yellow]"
                )
                continue
            filtered_items.append(item)
        return filtered_items

    def _item_identity(self, item: Any) -> tuple[str, str, str] | None:
        if isinstance(item, TweetSourceItem):
            return (item.source_name, item.content_type, item.identifier)
        if isinstance(item, dict) and "source_name" in item and "identifier" in item:
            return (
                item["source_name"],
                item.get("content_type", "unknown"),
                item["identifier"],
            )
        return None

    def _print_dedupe_summary(
        self,
        input_count: int,
        unique_count: int,
    ) -> None:
        if unique_count < input_count:
            duplicate_count = input_count - unique_count
            console.print(
                f"[blue]🔍 Deduplicated {duplicate_count} duplicate items[/blue]"
            )

    def _print_filter_summary(
        self,
        unique_count: int,
        filtered_count: int,
    ) -> None:
        if filtered_count < unique_count:
            skipped_count = unique_count - filtered_count
            console.print(
                f"[blue]📋 Filtered out {skipped_count} published items[/blue]"
            )


class SourceOrchestrator:
    """Orchestrate multiple sources running in parallel."""

    def __init__(self, max_workers: int = 4, total_per_run: int | None = None):
        self.max_workers = max_workers
        self.total_per_run = total_per_run

    def run_sources(
        self,
        source_configs: list[dict[str, Any]],
        targets: list[Any],
        api_keys_map: dict[str, list[str]],
        storage: Any,
        dry_run: bool = False,
        total_per_run: int | None = None,
    ) -> dict[str, Any]:
        """Run multiple sources in parallel, then publish to targets.

        Args:
            source_configs: List of configs with source instance and execute function
            targets: List of target instances
            api_keys_map: Dict mapping target class name to list of API keys
            storage: Storage service
            dry_run: If True, only generate without publishing

        Returns:
            Aggregated results from all sources
        """
        source_tasks, source_names = self._build_source_tasks(
            source_configs,
            dry_run,
        )

        # Execute all sources in parallel
        console.print(
            f"[blue]🚀 Starting {len(source_tasks)} sources in parallel[/blue]"
        )

        executor = ConcurrentExecutor(max_workers=self.max_workers)
        source_results = executor.run_parallel(source_tasks, source_names)

        total_stats = {
            "sources_executed": len(source_configs),
            "source_results": source_results,
        }

        all_items = self._aggregate_generated_items(source_results)

        if not all_items:
            console.print("[yellow]⚠️ No items generated from any source[/yellow]")
            return total_stats

        effective_limit = (
            total_per_run if total_per_run is not None else self.total_per_run
        )
        total_generated = len(all_items)

        if effective_limit is not None and len(all_items) > effective_limit:
            random.shuffle(all_items)
            all_items = all_items[:effective_limit]
            console.print(
                "[blue]🎯 Randomly selected "
                f"{effective_limit} items (total: {total_generated})[/blue]"
            )
            logger.info(
                "Randomly selected %s items out of %s generated",
                effective_limit,
                total_generated,
            )

        action = "Generating dry-run posts for" if dry_run else "Publishing"
        console.print(
            f"[blue]📤 {action} {len(all_items)} items "
            f"to {len(targets)} targets[/blue]"
        )

        publisher = SourceParallelPublisher(max_workers=self.max_workers)
        publish_results = publisher.publish_to_targets(
            tweets=all_items,
            targets=targets,
            api_keys_map=api_keys_map,
            storage=storage,
            dry_run=dry_run,
        )

        total_stats["publish_results"] = publish_results
        self._increment_collected_source_executions(source_results, storage, dry_run)
        return total_stats

    def _build_source_tasks(
        self,
        source_configs: list[dict[str, Any]],
        dry_run: bool,
    ) -> tuple[list[Callable[[], dict[str, Any]]], list[str]]:
        source_tasks: list[Callable[[], dict[str, Any]]] = []
        source_names = []

        for cfg in source_configs:
            source = cfg["source"]
            execute_fn = cfg.get("execute", "execute")
            limit = cfg.get("limit")
            source_name = source.__class__.__name__
            task_name = cfg.get("name") or f"{source_name}_{execute_fn}"
            storage_key = cfg.get("storage_key") or self._storage_key_for_workflow(
                source_name,
                execute_fn,
            )

            def create_source_task(
                src: Any,
                exec_fn: str,
                lim: Any,
                workflow_storage_key: str,
            ) -> Callable[[], dict[str, Any]]:
                def source_task() -> dict[str, Any]:
                    source_name = src.__class__.__name__
                    service_cls = self._get_service_for_source(source_name)
                    service = service_cls(dry_run=dry_run, limit=lim)
                    result = service.collect_items(exec_fn)
                    if isinstance(result, dict):
                        result["storage_key"] = workflow_storage_key
                        return result
                    return {"result": result, "storage_key": workflow_storage_key}

                return source_task

            source_tasks.append(
                create_source_task(source, execute_fn, limit, storage_key)
            )
            source_names.append(task_name)

        return source_tasks, source_names

    def _aggregate_generated_items(
        self,
        source_results: dict[str, TaskResult],
    ) -> list[Any]:
        all_items: list[Any] = []
        for result in source_results.values():
            if result.success:
                items = result.data.get("items_generated")
                if items is None:
                    items = result.data.get("tweets_generated", [])
                if isinstance(items, list):
                    all_items.extend(items)
        return all_items

    def _increment_collected_source_executions(
        self,
        source_results: dict[str, TaskResult],
        storage: Any,
        dry_run: bool,
    ) -> None:
        if dry_run:
            return

        incremented_keys: set[str] = set()
        for result in source_results.values():
            if not result.success:
                continue
            items = result.data.get("items_generated")
            if items is None:
                items = result.data.get("tweets_generated", [])
            if not isinstance(items, list) or not items:
                continue
            storage_key = result.data.get("storage_key")
            if not isinstance(storage_key, str) or storage_key in incremented_keys:
                continue
            storage.increment_daily_execution(storage_key)
            incremented_keys.add(storage_key)

    def _storage_key_for_workflow(self, source_name: str, execute_fn: str) -> str:
        workflow_storage_keys = {
            "FnSource": {
                "execute": "FnSource",
                "execute_calendar": "FnSourceCalendar",
                "execute_airdrops": "FnSourceAirdrops",
                "execute_fundraising": "FnSourceFundraising",
            },
            "FollowinSource": {
                "execute": "FollowinSource",
                "execute_topics": "FollowinSourceTopics",
                "execute_io_flow": "FollowinSourceIOFlow",
                "execute_discussion": "FollowinSourceDiscussion",
            },
            "PolymarketSource": {"execute": "PolymarketSource"},
            "PexelsSource": {"execute": "PexelsSource"},
            "SquareHotSource": {"execute": "SquareHotSource"},
            "BinanceAnnSource": {"execute": "BinanceAnnSource"},
        }
        return workflow_storage_keys.get(source_name, {}).get(execute_fn, source_name)

    def _get_service_for_source(self, source_name: str) -> Any:
        """Get the CLI service class for a source."""
        from binance_square_bot.services.cli import (
            BinanceAnnCliService,
            FnCliService,
            FollowinCliService,
            PexelsCliService,
            PolymarketCliService,
            SquareHotCliService,
        )

        service_map = {
            "FnSource": FnCliService,
            "PolymarketSource": PolymarketCliService,
            "FollowinSource": FollowinCliService,
            "PexelsSource": PexelsCliService,
            "SquareHotSource": SquareHotCliService,
            "BinanceAnnSource": BinanceAnnCliService,
        }

        return service_map.get(source_name, FnCliService)
