import sys
from loguru import logger
from ..config import config

def setup_logger():
    """Configure loguru logger with console and file outputs."""
    # Remove default handlers
    logger.remove()

    # Console output with colors
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level=config.log_level,
        colorize=True
    )

    # File output with rotation
    logger.add(
        "logs/app_{time:YYYY-MM-DD}.log",
        rotation="00:00",  # Rotate daily at midnight
        retention="30 days",
        compression="zip",
        level="DEBUG",
        encoding="utf-8"
    )
