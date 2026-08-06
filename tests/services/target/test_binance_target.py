from binance_square_bot.services.target.binance_target import BinanceTarget
from binance_square_bot.services.target.square_post import SquarePost

def test_binance_target_config():
    """Test BinanceTarget has correct config fields."""
    assert "api_keys" in BinanceTarget.Config.model_fields
    assert "api_url" in BinanceTarget.Config.model_fields
    assert "enabled" in BinanceTarget.Config.model_fields
    assert "daily_max_posts_per_key" in BinanceTarget.Config.model_fields

def test_filter_passthrough():
    """Test default filter passes through content."""
    target = BinanceTarget()
    assert target.filter("test content") == "test content"


def test_text_post_body_omits_content_type(tmp_path):
    """Plain text posts must NOT send contentType — sending contentType=0
    triggers "Content type not supported for OpenAPI" (regression from
    production error 2026-08-06).
    """
    target = BinanceTarget()
    # Stub out media (no upload needed for text) and capture the publish body.
    captured = {}

    class FakeResponse:
        status_code = 200
        def raise_for_status(self): pass
        def json(self): return {"code": "000000", "message": "", "data": {}}

    def fake_post(url, headers=None, json=None):
        captured["url"] = url
        captured["body"] = json
        return FakeResponse()

    target.client.post = fake_post
    post = SquarePost(post_type="text", body="hello world")
    ok, _ = target.publish(post, "test-key-1234567890")
    assert ok is True
    assert "contentType" not in captured["body"]
    assert captured["body"]["bodyTextOnly"] == "hello world"


def test_media_posts_include_content_type(tmp_path):
    """Image/article/video posts send the correct contentType."""
    img = tmp_path / "x.jpg"
    img.write_bytes(b"fake")
    target = BinanceTarget()

    # Stub media upload to return a URL without real network.
    ct_map = {"image": 1, "article": 2, "video": 3}
    def fake_build_body(post, api_key, key_mask):
        return {"contentType": ct_map[post.post_type], "bodyTextOnly": post.body}

    target._build_publish_body = fake_build_body  # type: ignore[method-assign]

    class FakeResponse:
        status_code = 200
        def raise_for_status(self): pass
        def json(self): return {"code": "000000", "data": {}}

    captured = {}
    def fake_post(url, headers=None, json=None):
        captured["body"] = json
        return FakeResponse()
    target.client.post = fake_post

    posts = [
        SquarePost(post_type="image", body="x" * 10, images=[str(img)]),
        SquarePost(post_type="article", body="x" * 10, title="T", cover=str(img)),
        SquarePost(post_type="video", body="x" * 10, video=str(img), video_duration=1.0),
    ]
    for post, expected_ct in zip(posts, [1, 2, 3]):
        captured.clear()
        target.publish(post, "test-key-1234567890")
        assert captured["body"]["contentType"] == expected_ct, post.post_type
