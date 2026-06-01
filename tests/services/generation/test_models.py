from binance_square_bot.services.generation.models import TweetSourceItem


def test_tweet_source_item_stores_source_content_fields():
    item = TweetSourceItem(
        source_name="FnSource",
        content_type="news",
        identifier="https://example.com/news/1",
        title="Title",
        summary="Summary",
        url="https://example.com/news/1",
        metadata={"foo": "bar"},
    )

    assert item.source_name == "FnSource"
    assert item.content_type == "news"
    assert item.identifier == "https://example.com/news/1"
    assert item.title == "Title"
    assert item.summary == "Summary"
    assert item.url == "https://example.com/news/1"
    assert item.metadata == {"foo": "bar"}


def test_tweet_source_item_to_prompt_payload_excludes_none_url():
    item = TweetSourceItem(
        source_name="FollowinSource",
        content_type="topics",
        identifier="123",
        title="Topic",
        summary="Summary",
    )

    payload = item.to_prompt_payload()

    assert payload["source_name"] == "FollowinSource"
    assert payload["content_type"] == "topics"
    assert payload["identifier"] == "123"
    assert "url" not in payload
