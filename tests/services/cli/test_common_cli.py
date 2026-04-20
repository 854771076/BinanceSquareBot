# tests/services/cli/test_common_cli.py
from binance_square_bot.services.cli.common_cli import CommonCliService


def test_common_cli_service_init():
    """Test CommonCliService can be initialized."""
    service = CommonCliService()
    assert service.storage is not None
