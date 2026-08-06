from typing import Dict, Any, List
from loguru import logger
from rich.console import Console

from binance_square_bot.services.storage import StorageService
from binance_square_bot.services.source.fn_source import FnSource
from binance_square_bot.services.source.followin_source import FollowinSource
from binance_square_bot.services.source.pexels_source import PexelsSource
from binance_square_bot.services.source.polymarket_source import PolymarketSource
from binance_square_bot.services.source.binance_ann_source import BinanceAnnSource
from binance_square_bot.services.source.square_hot_source import SquareHotSource
from binance_square_bot.services.target.binance_target import BinanceTarget
from binance_square_bot.services.concurrent_executor import SourceOrchestrator

console = Console()


class ParallelCliService:
    """CLI service for executing multiple sources in parallel."""

    def __init__(
        self,
        dry_run: bool = False,
        max_workers: int = 4,
        total_per_run: int = 15,
        enable_fn: bool = True,
        enable_fn_calendar: bool = True,
        enable_fn_airdrop: bool = True,
        enable_fn_fundraising: bool = True,
        enable_polymarket: bool = False,
        enable_followin_topics: bool = True,
        enable_followin_io_flow: bool = True,
        enable_followin_discussion: bool = True,
        enable_pexels: bool = False,
        enable_square_hot: bool = False,
        enable_binance_ann: bool = False,
        publish_workers: int = 1,
    ):
        self.dry_run = dry_run
        self.max_workers = max_workers
        self.total_per_run = total_per_run
        self.publish_workers = max(1, publish_workers)
        self.enable_fn = enable_fn
        self.enable_fn_calendar = enable_fn_calendar
        self.enable_fn_airdrop = enable_fn_airdrop
        self.enable_fn_fundraising = enable_fn_fundraising
        self.enable_polymarket = enable_polymarket
        self.enable_followin_topics = enable_followin_topics
        self.enable_followin_io_flow = enable_followin_io_flow
        self.enable_followin_discussion = enable_followin_discussion
        self.enable_pexels = enable_pexels
        self.enable_square_hot = enable_square_hot
        self.enable_binance_ann = enable_binance_ann
        self.storage = StorageService()
        self.source_limits = {
            "FnSource_execute": 4,
            "FnSource_execute_calendar": 1,
            "FnSource_execute_airdrops": 1,
            "FnSource_execute_fundraising": 1,
            "FollowinSource_execute_topics": 4,
            "FollowinSource_execute_io_flow": 4,
            "FollowinSource_execute_discussion": 4,
        }

    def execute_all(self) -> Dict[str, Any]:
        """Execute all enabled sources in parallel."""
        logger.info("Starting parallel execution of all enabled sources")

        source_configs: List[Dict[str, Any]] = []

        # FnSource - News
        if self.enable_fn:
            source_configs.append({
                "source": FnSource(),
                "execute": "execute",
                "limit": self.source_limits["FnSource_execute"],
            })
            console.print("[blue]✅ FnSource (news) enabled[/blue]")

        # FnSource - Calendar
        if self.enable_fn_calendar:
            source_configs.append({
                "source": FnSource(),
                "execute": "execute_calendar",
                "limit": self.source_limits["FnSource_execute_calendar"],
            })
            console.print("[blue]✅ FnSource (calendar) enabled[/blue]")

        # FnSource - Airdrop
        if self.enable_fn_airdrop:
            source_configs.append({
                "source": FnSource(),
                "execute": "execute_airdrops",
                "limit": self.source_limits["FnSource_execute_airdrops"],
            })
            console.print("[blue]✅ FnSource (airdrop) enabled[/blue]")

        # FnSource - Fundraising
        if self.enable_fn_fundraising:
            source_configs.append({
                "source": FnSource(),
                "execute": "execute_fundraising",
                "limit": self.source_limits["FnSource_execute_fundraising"],
            })
            console.print("[blue]✅ FnSource (fundraising) enabled[/blue]")

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
                "limit": self.source_limits["FollowinSource_execute_topics"],
            })
            console.print("[blue]✅ FollowinSource (topics) enabled[/blue]")

        # FollowinSource - IO Flow
        if self.enable_followin_io_flow:
            source_configs.append({
                "source": FollowinSource(),
                "execute": "execute_io_flow",
                "limit": self.source_limits["FollowinSource_execute_io_flow"],
            })
            console.print("[blue]✅ FollowinSource (io-flow) enabled[/blue]")

        # FollowinSource - Discussion
        if self.enable_followin_discussion:
            source_configs.append({
                "source": FollowinSource(),
                "execute": "execute_discussion",
                "limit": self.source_limits["FollowinSource_execute_discussion"],
            })
            console.print("[blue]✅ FollowinSource (discussion) enabled[/blue]")

        # Pexels is no longer an independent content source. When enabled it
        # attaches relevant cover/inline images to items AFTER aggregation (see
        # image_attributor below). Article posts get a cover; text posts become
        # image posts. Requires PEXELS_SOURCE_API_KEY.
        image_attributor = None
        if self.enable_pexels:
            pexels = PexelsSource()
            if pexels.config.api_key:
                image_attributor = pexels.attach_images
                console.print("[blue]✅ Pexels image attribution enabled[/blue]")
            else:
                console.print(
                    "[yellow]⚠️ Pexels requested but PEXELS_SOURCE_API_KEY "
                    "is missing; posting without images[/yellow]"
                )

        # SquareHotSource (opt-in — reverse-engineered feed, use carefully)
        if self.enable_square_hot:
            square_hot = SquareHotSource()
            if square_hot.config.enabled:
                source_configs.append({"source": square_hot, "execute": "execute"})
                console.print("[blue]✅ SquareHotSource enabled[/blue]")
            else:
                console.print(
                    "[yellow]⚠️ SquareHotSource requested but disabled "
                    "(SQUARE_HOT_SOURCE_ENABLED=true to enable); skipping[/yellow]"
                )

        # BinanceAnnSource (opt-in — official announcements, polished by AI)
        if self.enable_binance_ann:
            binance_ann = BinanceAnnSource()
            if binance_ann.config.enabled:
                source_configs.append({"source": binance_ann, "execute": "execute"})
                console.print("[blue]✅ BinanceAnnSource enabled[/blue]")
            else:
                console.print(
                    "[yellow]⚠️ BinanceAnnSource requested but disabled "
                    "(BINANCE_ANN_SOURCE_ENABLED=true to enable); skipping[/yellow]"
                )

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
            total_per_run=self.total_per_run,
            image_attributor=image_attributor,
            publish_workers=self.publish_workers,
        )

        logger.info(f"Parallel execution complete: {results}")
        return results
