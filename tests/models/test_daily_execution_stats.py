from binance_square_bot.models.base import Database
from binance_square_bot.models.daily_execution_stats import DailyExecutionStatsModel

def test_today_date_format():
    """Test today() returns YYYY-MM-DD format."""
    date_str = DailyExecutionStatsModel.today()
    assert len(date_str) == 10
    assert date_str[4] == "-"
    assert date_str[7] == "-"

def test_can_execute():
    """Test can_execute logic."""
    stat = DailyExecutionStatsModel(count=5)
    assert stat.can_execute(10) is True
    assert stat.can_execute(5) is False

def test_model_persistence():
    """Test model can be saved and queried."""
    Database.init(":memory:")

    with Database.get_session() as session:
        stat = DailyExecutionStatsModel(
            source_name="TestSource",
            date=DailyExecutionStatsModel.today(),
            count=3
        )
        session.add(stat)
        session.commit()

        result = session.query(DailyExecutionStatsModel).filter_by(
            source_name="TestSource"
        ).first()
        assert result.count == 3
