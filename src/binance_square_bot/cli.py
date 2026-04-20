"""CLI entry point for BinanceSquareBot."""

import typer
from rich.console import Console

from binance_square_bot.common.logging import setup_logger
from binance_square_bot.services.cli import FnCliService, PolymarketCliService, FollowinCliService, CommonCliService

# Initialize logger
setup_logger()

app = typer.Typer(
    name="binance-square-bot",
    help="BinanceSquareBot - Auto-crawl news, generate AI tweets, publish to Binance Square",
    add_completion=False,
)

polymarket_app = typer.Typer(
    help="Polymarket AI research tweets",
    add_completion=False,
)
app.add_typer(polymarket_app, name="polymarket-research")

followin_app = typer.Typer(
    help="Followin AI hot topics and token analysis",
    add_completion=False,
)
app.add_typer(followin_app, name="followin")

console = Console()


def version_callback(value: bool) -> None:
    if value:
        from . import __version__
        console.print(f"BinanceSquareBot v{__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool | None = typer.Option(
        None,
        "--version",
        "-v",
        help="Show version number",
        callback=version_callback,
        is_eager=True,
    ),
) -> None:
    pass


@app.command("run")
def run(
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Only fetch and generate, no actual publishing",
    ),
    limit: int | None = typer.Option(
        None,
        "--limit",
        help="Limit number of articles to process (for testing)",
    ),
) -> None:
    """Run full Fn news crawl-generate-publish workflow."""
    service = FnCliService(dry_run=dry_run, limit=limit)
    service.execute()


@app.command("calendar")
def run_calendar(
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Only fetch and generate, no actual publishing",
    ),
    limit: int | None = typer.Option(
        None,
        "--limit",
        help="Limit number of events to process (for testing)",
    ),
) -> None:
    """Run Fn calendar events workflow - fetch events, generate tweets, publish."""
    service = FnCliService(dry_run=dry_run, limit=limit)
    service.execute_calendar()


@app.command("airdrop")
def run_airdrop(
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Only fetch and generate, no actual publishing",
    ),
    limit: int | None = typer.Option(
        None,
        "--limit",
        help="Limit number of airdrops to process (for testing)",
    ),
) -> None:
    """Run Fn airdrop events workflow - fetch airdrops, generate tweets, publish."""
    service = FnCliService(dry_run=dry_run, limit=limit)
    service.execute_airdrops()


@app.command("fundraising")
def run_fundraising(
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Only fetch and generate, no actual publishing",
    ),
    limit: int | None = typer.Option(
        None,
        "--limit",
        help="Limit number of fundraising events to process (for testing)",
    ),
) -> None:
    """Run Fn fundraising (众筹) events workflow - fetch events, generate tweets, publish."""
    service = FnCliService(dry_run=dry_run, limit=limit)
    service.execute_fundraising()


@app.command("clean")
def clean(
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Skip confirmation prompt",
    ),
) -> None:
    """Clean all processed URL records and daily stats."""
    service = CommonCliService()
    service.clean(force=force)


@polymarket_app.command("run")
def polymarket_run(
    dry_run: bool = typer.Option(False, "--dry-run", help="Only generate, no publishing"),
) -> None:
    """Run Polymarket research workflow - fetch markets, generate tweets, publish."""
    service = PolymarketCliService(dry_run=dry_run)
    service.execute()


@polymarket_app.command("scan")
def polymarket_scan(
    top_n: int = typer.Option(5, "--top-n", help="Show top N candidate markets"),
) -> None:
    """Scan Polymarket markets and show top candidates - no generation/publishing."""
    service = PolymarketCliService()
    service.scan(top_n=top_n)


@followin_app.command("run")
def followin_run(
    dry_run: bool = typer.Option(False, "--dry-run", help="Only generate, no publishing"),
    limit: int | None = typer.Option(None, "--limit", help="Limit number of items to process"),
) -> None:
    """Run Followin full workflow - fetch all topics/tokens, generate tweets, publish."""
    service = FollowinCliService(dry_run=dry_run, limit=limit)
    service.execute()


@followin_app.command("topics")
def followin_topics(
    dry_run: bool = typer.Option(False, "--dry-run", help="Only generate, no publishing"),
    limit: int | None = typer.Option(None, "--limit", help="Limit number of items to process"),
) -> None:
    """Run Followin trending topics workflow."""
    service = FollowinCliService(dry_run=dry_run, limit=limit)
    service.execute_topics()


@followin_app.command("io-flow")
def followin_io_flow(
    dry_run: bool = typer.Option(False, "--dry-run", help="Only generate, no publishing"),
    limit: int | None = typer.Option(None, "--limit", help="Limit number of items to process"),
) -> None:
    """Run Followin IO flow tokens workflow."""
    service = FollowinCliService(dry_run=dry_run, limit=limit)
    service.execute_io_flow()


@followin_app.command("discussion")
def followin_discussion(
    dry_run: bool = typer.Option(False, "--dry-run", help="Only generate, no publishing"),
    limit: int | None = typer.Option(None, "--limit", help="Limit number of items to process"),
) -> None:
    """Run Followin discussion tokens workflow."""
    service = FollowinCliService(dry_run=dry_run, limit=limit)
    service.execute_discussion()


if __name__ == "__main__":
    app()
