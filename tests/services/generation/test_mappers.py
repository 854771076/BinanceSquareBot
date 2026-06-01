from datetime import datetime, timezone

from binance_square_bot.services.generation.mappers import (
    fn_airdrop_to_item,
    fn_article_to_item,
    fn_calendar_to_item,
    fn_fundraising_to_item,
    followin_item_to_item,
    polymarket_to_item,
)
from binance_square_bot.services.source.fn_source import (
    AirdropEvent,
    Article,
    CalendarEvent,
    FundraisingEvent,
)
from binance_square_bot.services.source.followin_source import FollowinToken, FollowinTopic
from binance_square_bot.services.source.polymarket_source import PolymarketMarket


def test_fn_article_to_item_maps_news_article_fields():
    published_at = datetime(2026, 6, 1, 12, 30, tzinfo=timezone.utc)
    article = Article(
        title="Bitcoin ETF sees inflows",
        url="https://foresightnews.pro/news/1",
        content="Spot ETF demand accelerated today.",
        published_at=published_at,
    )

    item = fn_article_to_item(article)

    assert item.source_name == "FnSource"
    assert item.content_type == "news"
    assert item.identifier == article.url
    assert item.url == article.url
    assert item.title == article.title
    assert item.summary == article.content
    assert item.metadata == {"published_at": published_at.isoformat()}


def test_fn_article_to_item_maps_missing_published_at_to_none():
    article = Article(
        title="Market update",
        url="https://foresightnews.pro/news/2",
        content="No timestamp was provided.",
    )

    item = fn_article_to_item(article)

    assert item.metadata == {"published_at": None}


def test_fn_calendar_to_item_maps_calendar_event_fields():
    start_time = datetime(2026, 6, 2, 8, 0, tzinfo=timezone.utc)
    end_time = datetime(2026, 6, 2, 10, 0, tzinfo=timezone.utc)
    event = CalendarEvent(
        title="Protocol mainnet launch",
        url="https://foresightnews.pro/calendar/1",
        description="The protocol plans to launch mainnet.",
        start_time=start_time,
        end_time=end_time,
        category=7,
    )

    item = fn_calendar_to_item(event)

    assert item.source_name == "FnSource"
    assert item.content_type == "calendar"
    assert item.identifier == event.url
    assert item.url == event.url
    assert item.title == event.title
    assert item.summary == event.description
    assert item.metadata == {
        "start_time": start_time.isoformat(),
        "end_time": end_time.isoformat(),
        "category": 7,
    }


def test_fn_calendar_to_item_maps_missing_times_to_none():
    event = CalendarEvent(
        title="AMA",
        url="https://foresightnews.pro/calendar/2",
        description="Community AMA.",
    )

    item = fn_calendar_to_item(event)

    assert item.metadata == {
        "start_time": None,
        "end_time": None,
        "category": None,
    }


def test_fn_airdrop_to_item_maps_airdrop_event_fields():
    published_at = datetime(2026, 6, 3, 9, 45, tzinfo=timezone.utc)
    event = AirdropEvent(
        id=42,
        title="Layer 2 airdrop opens",
        url="https://foresightnews.pro/airdrop/42",
        brief="Eligible users can claim tokens.",
        published_at=published_at,
    )

    item = fn_airdrop_to_item(event)

    assert item.source_name == "FnSource"
    assert item.content_type == "airdrop"
    assert item.identifier == event.url
    assert item.url == event.url
    assert item.title == event.title
    assert item.summary == event.brief
    assert item.metadata == {"id": 42, "published_at": published_at.isoformat()}


def test_fn_fundraising_to_item_maps_fundraising_event_fields():
    date = datetime(2026, 6, 4, 14, 15, tzinfo=timezone.utc)
    event = FundraisingEvent(
        id=100,
        project_name="DeFi Labs",
        amount=12_500_000.0,
        round_str="Series A",
        description="DeFi Labs raised capital to expand liquidity products.",
        investors=["Dragonfly", "Paradigm"],
        url="https://foresightnews.pro/fundraising/100",
        date=date,
    )

    item = fn_fundraising_to_item(event)

    assert item.source_name == "FnSource"
    assert item.content_type == "fundraising"
    assert item.identifier == event.url
    assert item.url == event.url
    assert item.title == event.project_name
    assert item.summary == event.description
    assert item.metadata == {
        "id": 100,
        "amount": 12_500_000.0,
        "round": "Series A",
        "investors": ["Dragonfly", "Paradigm"],
        "date": date.isoformat(),
    }


def test_fn_fundraising_to_item_maps_missing_date_to_none():
    event = FundraisingEvent(
        id=101,
        project_name="Wallet Co",
        description="Wallet Co raised an undisclosed round.",
        investors=[],
        url="https://foresightnews.pro/fundraising/101",
    )

    item = fn_fundraising_to_item(event)

    assert item.metadata["date"] is None


def test_followin_item_to_item_maps_topic_fields():
    topic = FollowinTopic(
        id=123,
        title="Stablecoin regulation heats up",
        summary="New policy debates are trending among crypto users.",
        url="https://followin.io/zh-Hans/trendingTopic/123",
    )

    item = followin_item_to_item(topic)

    assert item.source_name == "FollowinSource"
    assert item.content_type == "topics"
    assert item.identifier == "123"
    assert item.url == topic.url
    assert item.title == topic.title
    assert item.summary == topic.summary
    assert item.metadata == {}


def test_followin_item_to_item_maps_token_fields():
    token_quote = {"price": "12.34", "change_24h": "5%"}
    token = FollowinToken(
        id=456,
        name="Solana",
        symbol="SOL",
        summary="SOL discussion volume is rising.",
        category="discussion",
        token_quote=token_quote,
    )

    item = followin_item_to_item(token)

    assert item.source_name == "FollowinSource"
    assert item.content_type == "token"
    assert item.identifier == "456"
    assert item.url is None
    assert item.title == "Solana ($SOL)"
    assert item.summary == token.summary
    assert item.metadata == {
        "name": "Solana",
        "symbol": "SOL",
        "category": "discussion",
        "token_quote": token_quote,
    }


def test_polymarket_to_item_maps_market_fields_with_description():
    market = PolymarketMarket(
        condition_id="0xabc",
        question="Will ETH hit $5k in 2026?",
        yes_price=0.62,
        no_price=0.38,
        volume=250_000.0,
        image="https://example.com/eth.png",
        description="A market about ETH price performance.",
    )

    item = polymarket_to_item(market)

    assert item.source_name == "PolymarketSource"
    assert item.content_type == "polymarket_research"
    assert item.identifier == "0xabc"
    assert item.url is None
    assert item.title == market.question
    assert item.summary == market.description
    assert item.metadata == {
        "condition_id": "0xabc",
        "yes_price": 0.62,
        "no_price": 0.38,
        "volume": 250_000.0,
        "image": "https://example.com/eth.png",
    }


def test_polymarket_to_item_falls_back_to_question_when_description_missing():
    market = PolymarketMarket(
        condition_id="0xdef",
        question="Will BTC dominance exceed 60%?",
        yes_price=0.41,
        no_price=0.59,
        volume=10_000.0,
    )

    item = polymarket_to_item(market)

    assert item.summary == market.question
    assert item.metadata["image"] is None
