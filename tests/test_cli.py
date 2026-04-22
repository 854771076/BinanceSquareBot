from typer.testing import CliRunner
from binance_square_bot.cli import app

runner = CliRunner()


def test_version():
    """Test version flag works."""
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "BinanceSquareBot" in result.output


def test_help():
    """Test help command works."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "run" in result.output
    assert "clean" in result.output


def test_parallel_help_has_total_per_run():
    """Test parallel command help includes --total-per-run option."""
    result = runner.invoke(app, ["parallel", "--help"])
    assert result.exit_code == 0
    assert "--total-per-run" in result.output
    assert "Max total articles to publish" in result.output
