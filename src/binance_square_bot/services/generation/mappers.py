from datetime import datetime

from binance_square_bot.services.generation.models import TweetSourceItem
from binance_square_bot.services.source.fn_source import (
    AirdropEvent,
    Article,
    CalendarEvent,
    FundraisingEvent,
)
from binance_square_bot.services.source.followin_source import FollowinToken, FollowinTopic
from binance_square_bot.services.source.polymarket_source import PolymarketMarket


def _isoformat(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def fn_article_to_item(article: Article) -> TweetSourceItem:
    return TweetSourceItem(
        source_name="FnSource",
        content_type="news",
        identifier=article.url,
        title=article.title,
        summary=article.content,
        url=article.url,
        metadata={"published_at": _isoformat(article.published_at)},
    )


def fn_calendar_to_item(event: CalendarEvent) -> TweetSourceItem:
    return TweetSourceItem(
        source_name="FnSource",
        content_type="calendar",
        identifier=event.url,
        title=event.title,
        summary=event.description,
        url=event.url,
        metadata={
            "start_time": _isoformat(event.start_time),
            "end_time": _isoformat(event.end_time),
            "category": event.category,
        },
    )


def fn_airdrop_to_item(event: AirdropEvent) -> TweetSourceItem:
    return TweetSourceItem(
        source_name="FnSource",
        content_type="airdrop",
        identifier=event.url,
        title=event.title,
        summary=event.brief,
        url=event.url,
        metadata={"id": event.id, "published_at": _isoformat(event.published_at)},
    )


def fn_fundraising_to_item(event: FundraisingEvent) -> TweetSourceItem:
    return TweetSourceItem(
        source_name="FnSource",
        content_type="fundraising",
        identifier=event.url,
        title=event.project_name,
        summary=event.description,
        url=event.url,
        metadata={
            "id": event.id,
            "amount": event.amount,
            "round": event.round_str,
            "investors": event.investors,
            "date": _isoformat(event.date),
        },
    )


def followin_item_to_item(item: FollowinTopic | FollowinToken) -> TweetSourceItem:
    if isinstance(item, FollowinTopic):
        return TweetSourceItem(
            source_name="FollowinSource",
            content_type="topics",
            identifier=str(item.id),
            title=item.title,
            summary=item.summary,
            url=item.url,
        )

    return TweetSourceItem(
        source_name="FollowinSource",
        content_type="token",
        identifier=str(item.id),
        title=f"{item.name} (${item.symbol})",
        summary=item.summary,
        metadata={
            "name": item.name,
            "symbol": item.symbol,
            "category": item.category,
            "token_quote": item.token_quote,
        },
    )


def polymarket_to_item(market: PolymarketMarket) -> TweetSourceItem:
    return TweetSourceItem(
        source_name="PolymarketSource",
        content_type="polymarket_research",
        identifier=market.condition_id,
        title=market.question,
        summary=market.description or market.question,
        metadata={
            "condition_id": market.condition_id,
            "yes_price": market.yes_price,
            "no_price": market.no_price,
            "volume": market.volume,
            "image": market.image,
        },
    )
