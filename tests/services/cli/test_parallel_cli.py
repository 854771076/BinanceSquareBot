# tests/services/cli/test_parallel_cli.py
from binance_square_bot.services.cli.parallel_cli import ParallelCliService


def test_parallel_cli_service_initializes_source_limits():
    """Test ParallelCliService initializes with correct default source_limits."""
    service = ParallelCliService()

    expected_limits = {
        "FnSource_execute": 2,
        "FnSource_execute_calendar": 1,
        "FnSource_execute_airdrops": 1,
        "FnSource_execute_fundraising": 1,
        "FollowinSource_execute_topics": 1,
        "FollowinSource_execute_io_flow": 1,
        "FollowinSource_execute_discussion": 1,
    }

    assert service.source_limits == expected_limits
    assert len(service.source_limits) == 7


def test_source_configs_have_correct_limit_values():
    """Test that each source_config gets the correct limit value from source_limits."""
    service = ParallelCliService(
        enable_polymarket=False,  # Polymarket doesn't need limit
    )

    # Build source_configs the same way execute_all does
    source_configs = []

    # FnSource - News
    if service.enable_fn:
        source_configs.append({
            "execute": "execute",
            "limit": service.source_limits["FnSource_execute"],
        })

    # FnSource - Calendar
    if service.enable_fn_calendar:
        source_configs.append({
            "execute": "execute_calendar",
            "limit": service.source_limits["FnSource_execute_calendar"],
        })

    # FnSource - Airdrop
    if service.enable_fn_airdrop:
        source_configs.append({
            "execute": "execute_airdrops",
            "limit": service.source_limits["FnSource_execute_airdrops"],
        })

    # FnSource - Fundraising
    if service.enable_fn_fundraising:
        source_configs.append({
            "execute": "execute_fundraising",
            "limit": service.source_limits["FnSource_execute_fundraising"],
        })

    # FollowinSource - Topics
    if service.enable_followin_topics:
        source_configs.append({
            "execute": "execute_topics",
            "limit": service.source_limits["FollowinSource_execute_topics"],
        })

    # FollowinSource - IO Flow
    if service.enable_followin_io_flow:
        source_configs.append({
            "execute": "execute_io_flow",
            "limit": service.source_limits["FollowinSource_execute_io_flow"],
        })

    # FollowinSource - Discussion
    if service.enable_followin_discussion:
        source_configs.append({
            "execute": "execute_discussion",
            "limit": service.source_limits["FollowinSource_execute_discussion"],
        })

    # Verify all 7 sources have limits
    assert len(source_configs) == 7

    # Verify each source has the correct limit value
    limits_by_execute = {cfg["execute"]: cfg["limit"] for cfg in source_configs}

    assert limits_by_execute["execute"] == 2  # Fn news
    assert limits_by_execute["execute_calendar"] == 1
    assert limits_by_execute["execute_airdrops"] == 1
    assert limits_by_execute["execute_fundraising"] == 1
    assert limits_by_execute["execute_topics"] == 1
    assert limits_by_execute["execute_io_flow"] == 1
    assert limits_by_execute["execute_discussion"] == 1
