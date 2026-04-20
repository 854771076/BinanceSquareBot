from binance_square_bot.services.cli.fn_cli import FnCliService

def test_fn_cli_service_init():
    """Test FnCliService can be initialized."""
    service = FnCliService(dry_run=True, limit=5)
    assert service.dry_run is True
    assert service.limit == 5
