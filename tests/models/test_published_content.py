from binance_square_bot.models.published_content import PublishedContentModel
from binance_square_bot.models.base import Database


def test_today_date_format():
    """Test today() returns YYYY-MM-DD format."""
    date_str = PublishedContentModel.today()
    assert isinstance(date_str, str)
    assert len(date_str) == 10  # YYYY-MM-DD
    assert date_str[4] == "-"
    assert date_str[7] == "-"


def test_content_hashing():
    """Test content hashing produces consistent SHA256 hex hash."""
    content_url = "https://example.com/article/123"
    hash1 = PublishedContentModel.hash_content(content_url)
    hash2 = PublishedContentModel.hash_content(content_url)
    assert hash1 == hash2
    assert len(hash1) == 64  # SHA256 hex


def test_model_persistence():
    """Test model can be saved and queried by composite primary key."""
    Database.init(":memory:")

    content_url = "https://example.com/article/123"
    content_hash = PublishedContentModel.hash_content(content_url)

    with Database.get_session() as session:
        content = PublishedContentModel(
            content_hash=content_hash,
            source_name="TestSource",
            content_type="article",
            date=PublishedContentModel.today()
        )
        session.add(content)
        session.commit()

        result = session.query(PublishedContentModel).filter_by(
            content_hash=content_hash,
            source_name="TestSource",
            content_type="article",
            date=PublishedContentModel.today()
        ).first()
        assert result is not None
        assert result.source_name == "TestSource"
        assert result.content_type == "article"
