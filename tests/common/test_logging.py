from loguru import logger
from binance_square_bot.common.logging import setup_logger

def test_setup_logger():
    """Test setup_logger configures logger handlers."""
    initial_handler_count = len(logger._core.handlers)
    setup_logger()
    # Should have at least stderr handler after setup
    assert len(logger._core.handlers) >= 1

def test_logger_usage():
    """Test logger can be used after setup."""
    setup_logger()
    logger.info("Test log message")
    # No exception = success
    assert True
