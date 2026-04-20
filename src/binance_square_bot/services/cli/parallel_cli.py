from typing import Dict, Any, List
from loguru import logger
from rich.console import Console

from binance_square_bot.services.storage import StorageService
from binance_square_bot.services.source.fn_source import FnSource
from binance_square_bot.services.source.polymarket_source import PolymarketSource
from binance_square_bot.services.source.followin_source import FollowinSource
from binance_square_bot.services.target.binance_target import BinanceTarget
from binance_square_bot.services.concurrent_executor import SourceOrchestrator

console = Console()


class ParallelCliService:
    """CLI service for executing multiple sources in parallel."""

    def __init__(
        self,
        dry_run: bool = False,
        max_workers: int = 4,
        enable_fn: bool = True,
        enable_polymarket: bool = False,
        enable_followin_topics: bool = True,
        enable_followin_io_flow: bool = True,
        enable_followin_discussion: bool = True,
    ):
        self.dry_run = dry_run
        self.max_workers = max_workers
        self.enable_fn = enable_fn
        self.enable_polymarket = enable_polymarket
        self.enable_followin_topics = enable_followin_topics
        self.enable_followin_io_flow = enable_followin_io_flow
        self.enable_followin_discussion = enable_followin_discussion
        self.storage = StorageService()

    def execute_all(self) -> Dict[str, Any]:
        """Execute all enabled sources in parallel."""
        logger.info("Starting parallel execution of all enabled sources")

        source_configs: List[Dict[str, Any]] = []

        # FnSource
        if self.enable_fn:
            source_configs.append({
                "source": FnSource(),
                "execute": "execute",
            })
            console.print("[blue]✅ FnSource enabled[/blue]")

        # PolymarketSource
        if self.enable_polymarket:
            source_configs.append({
                "source": PolymarketSource(),
                "execute": "execute",
            })
            console.print("[blue]✅ PolymarketSource enabled[/blue]")

        # FollowinSource - Topics
        if self.enable_followin_topics:
            source_configs.append({
                "source": FollowinSource(),
                "execute": "execute_topics",
            })
            console.print("[blue]✅ FollowinSource (topics) enabled[/blue]")

        # FollowinSource - IO Flow
        if self.enable_followin_io_flow:
            source_configs.append({
                "source": FollowinSource(),
                "execute": "execute_io_flow",
            })
            console.print("[blue]✅ FollowinSource (io-flow) enabled[/blue]")

        # FollowinSource - Discussion
        if self.enable_followin_discussion:
            source_configs.append({
                "source": FollowinSource(),
                "execute": "execute_discussion",
            })
            console.print("[blue]✅ FollowinSource (discussion) enabled[/blue]")

        if not source_configs:
            console.print("[red]❌ No sources enabled[/red]")
            return {"error": "no sources enabled"}

        # Initialize targets
        targets = [BinanceTarget()]
        api_keys_map = {
            "BinanceTarget": targets[0].config.api_keys,
        }

        # Create orchestrator and run
        orchestrator = SourceOrchestrator(max_workers=self.max_workers)
        results = orchestrator.run_sources(
            source_configs=source_configs,
            targets=targets,
            api_keys_map=api_keys_map,
            storage=self.storage,
            dry_run=self.dry_run,
        )

        logger.info(f"Parallel execution complete: {results}")
        return results
