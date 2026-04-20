# src/binance_square_bot/services/cli/common_cli.py
import os
from loguru import logger
from rich.console import Console
from rich.prompt import Confirm

from binance_square_bot.services.storage import StorageService
from binance_square_bot.config import config

console = Console()


class CommonCliService:
    """Common CLI commands service."""
    
    def __init__(self):
        self.storage = StorageService()
    
    def clean(self, force: bool = False) -> None:
        """Clean all processed URL records and daily stats.
        
        Args:
            force: If True, skip confirmation prompt
        """
        if not force:
            confirmed = Confirm.ask(
                "[bold red]⚠️ Are you sure you want to CLEAR ALL processed records? This cannot be undone.[/bold red]"
            )
            if not confirmed:
                console.print("[yellow]Operation cancelled[/yellow]")
                return
        
        # Delete database file
        db_path = config.sqlite_db_path
        if os.path.exists(db_path):
            os.remove(db_path)
            logger.info(f"Deleted database file: {db_path}")
            console.print("[green]✅ All processed records have been cleared[/green]")
        else:
            console.print("[yellow]Database file not found, nothing to clean[/yellow]")
