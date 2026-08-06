"""Binance Square hot-post source (reverse-engineered 2026-08-06).

Real protocol captured from a browser session to https://www.binance.com/en/square
(artifacts in js_reverse_cache/):

  List:
    POST /bapi/composite/v9/friendly/pgc/feed/feed-recommend/list
    headers: clienttype=web, lang=en, versioncode=web
             (versioncode is the gating header)
    body:    {"pageIndex":1,"pageSize":20,"scene":"web-homepage","contentIds":[]}
    resp:    data.vos[] = {id, title, subTitle, authorName,
                           authorVerificationType, likeCount, ...}

  Detail:
    GET  /bapi/composite/v3/friendly/pgc/special/content/detail/{id}
    headers: same as above
    resp:    data = {id, title, bodyTextOnly (plain text), tokensBodyMap ({SYM: {...}}),
                     hashtagIdentifyList, likeCount, commentCount, shareCount, viewCount,
                     contentAuthor, username, authorVerificationType, contentType,
                     imageList, isCreatedByAI, ...}

No signatures, cookies, WASM, or bootstrap. Pure httpx.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Any

import httpx
from loguru import logger
from pydantic import BaseModel

from binance_square_bot.services.base import BaseSource
from binance_square_bot.services.generation.models import TweetSourceItem

BASE_URL = "https://www.binance.com"
LIST_ENDPOINT = "/bapi/composite/v9/friendly/pgc/feed/feed-recommend/list"
DETAIL_ENDPOINT = "/bapi/composite/v3/friendly/pgc/special/content/detail"

DEFAULT_HEADERS = {
    "clienttype": "web",
    "lang": "en",
    "versioncode": "web",
    "referer": "https://www.binance.com/en/square",
    "user-agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36"
    ),
    "content-type": "application/json",
}


class SquareHotPost(BaseModel):
    post_id: str
    author_id: str
    author_name: str
    username: str | None = None
    author_verified: bool = False
    title: str | None = None
    body: str
    coin_tags: list[str] = []
    hashtags: list[str] = []
    like_count: int = 0
    comment_count: int = 0
    share_count: int = 0
    view_count: int = 0
    content_type: int = 1  # 1=text, 2=long article
    is_ai: bool = False


class SquareHotSource(BaseSource):
    """Fetch trending Square posts for AI-rewritten republication."""

    # Binance-official accounts — rewriting their platform-relevant content
    # gets traffic boost per project guidance #2. We still rewrite aggressively
    # (lower similarity threshold) and never re-host their images.

    class Config(BaseSource.Config):
        enabled: bool = False
        daily_max_executions: int = 1
        list_endpoint: str = LIST_ENDPOINT
        detail_endpoint: str = DETAIL_ENDPOINT
        page_size: int = 20
        max_items_per_run: int = 5
        # Only fetch detail for items that pass list-level filters.
        min_like_count: int = 50
        min_view_count: int = 0
        skip_verified_authors: bool = True
        # Binance-official verified authors bypass skip_verified_authors.
        official_author_whitelist: list[str] = [
            "binance_news",
            "binance",
            "binance_research",
            "binance_announcements",
            "binance_alpha",
            "binance_square",
            "binance_academy",
            "cz",
        ]
        skip_ai_content: bool = True
        min_content_chars: int = 200
        max_content_chars: int = 6000
        # Same-script rewrite gate: SequenceMatcher ratio in [0,1].
        # Cross-script pairs (EN original -> CN rewrite) always pass because the
        # language shift itself is sufficient transformation; this only blocks
        # CN->CN or EN->EN synonym-swap rewrites. Higher = more lenient.
        similarity_threshold: float = 0.8
        # Stricter gate for official-account same-script rewrites.
        official_similarity_threshold: float = 0.7
        request_timeout: float = 15.0
        scene: str = "web-homepage"
        lang: str = "en"

    def __init__(self) -> None:
        super().__init__()
        headers = dict(DEFAULT_HEADERS)
        headers["lang"] = self.config.lang
        self._client = httpx.Client(
            timeout=self.config.request_timeout,
            headers=headers,
            base_url=BASE_URL,
        )

    # ----- BaseSource contract -----

    def fetch(self) -> list[TweetSourceItem]:
        listings = self._fetch_list()
        listings = self._filter_listings(listings)
        # Fetch details concurrently — each is an independent HTTP round-trip.
        target_count = self.config.max_items_per_run
        candidates: list[SquareHotPost | None] = []
        # Fetch a few extra listings concurrently so that post-filter rejections
        # (verification, length, AI content) don't force a second serial batch.
        wanted = min(len(listings), target_count + 4)
        with ThreadPoolExecutor(max_workers=min(6, wanted or 1)) as pool:
            for post in pool.map(
                self._fetch_detail, [v["id"] for v in listings[:wanted]]
            ):
                candidates.append(post)

        items: list[TweetSourceItem] = []
        for post in candidates:
            if post is None or not self._passes_detail_filters(post):
                continue
            items.append(self._to_item(post))
            if len(items) >= target_count:
                break
        return items

    def generate(self, data: Any) -> Any:
        return data

    # ----- list -----

    def _fetch_list(self) -> list[dict]:
        body = {
            "pageIndex": 1,
            "pageSize": self.config.page_size,
            "scene": self.config.scene,
            "contentIds": [],
        }
        response = self._client.post(self.config.list_endpoint, json=body)
        response.raise_for_status()
        payload = response.json()
        if str(payload.get("code")) not in ("000000", "0"):
            raise RuntimeError(f"feed list error: {payload.get('message')} ({payload.get('code')})")
        data = payload.get("data") or {}
        return data.get("vos") or []

    def _is_whitelisted_author(self, username: str | None, author_name: str | None = None) -> bool:
        """Match the unique handle only. Display name (authorName) is spoofable
        and must NOT grant verified-skip. Normalize punctuation so
        'Binance_News' matches 'binancenews'.
        """
        del author_name  # explicitly ignored — do not trust display name
        if not username:
            return False

        def _norm(s: str) -> str:
            return s.strip().lower().replace("_", "").replace("-", "")

        normalized = _norm(username)
        allowed = {_norm(u) for u in self.config.official_author_whitelist}
        return normalized in allowed

    def _filter_listings(self, listings: list[dict]) -> list[dict]:
        result = []
        for v in listings:
            if not v.get("id") or not v.get("subTitle"):
                continue
            verified = int(v.get("authorVerificationType") or 0) >= 2
            # username is the unique handle; authorName is display name and is
            # not used for whitelist matching (spoofable).
            username = v.get("username")
            whitelisted = self._is_whitelisted_author(
                str(username) if username else None,
            )
            if verified and self.config.skip_verified_authors and not whitelisted:
                continue
            # Official-account posts are worth rewriting regardless of
            # engagement; apply the like-count floor only to non-whitelisted
            # community posts.
            if not whitelisted and int(v.get("likeCount") or 0) < self.config.min_like_count:
                continue
            result.append(v)
        return result

    # ----- detail -----

    def _fetch_detail(self, post_id: str | int) -> SquareHotPost | None:
        try:
            response = self._client.get(f"{self.config.detail_endpoint}/{post_id}")
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPError as exc:
            logger.warning(f"SquareHot detail failed for {post_id}: {exc}")
            return None
        if str(payload.get("code")) not in ("000000", "0"):
            logger.warning(f"SquareHot detail error for {post_id}: {payload.get('message')}")
            return None
        data = payload.get("data")
        if not isinstance(data, dict):
            return None
        return self._parse_detail(data)

    @staticmethod
    def _parse_detail(data: dict) -> SquareHotPost:
        tokens = data.get("tokensBodyMap") or {}
        coin_tags = [str(sym).upper() for sym in tokens.keys() if sym]
        hashtags = [str(t).lstrip("#") for t in (data.get("hashtagIdentifyList") or [])]
        author_id = str(data.get("squareUid") or data.get("binanceUid") or "")
        return SquareHotPost(
            post_id=str(data.get("id") or ""),
            author_id=author_id,
            author_name=str(data.get("contentAuthor") or data.get("displayName") or "unknown"),
            username=data.get("username"),
            author_verified=int(data.get("authorVerificationType") or 0) >= 2,
            title=data.get("title"),
            body=str(data.get("bodyTextOnly") or "").strip(),
            coin_tags=coin_tags,
            hashtags=hashtags,
            like_count=int(data.get("likeCount") or 0),
            comment_count=int(data.get("commentCount") or 0),
            share_count=int(data.get("shareCount") or 0),
            view_count=int(data.get("viewCount") or 0),
            content_type=int(data.get("contentType") or 1),
            is_ai=bool(data.get("isCreatedByAI")),
        )

    def _passes_detail_filters(self, post: SquareHotPost) -> bool:
        if not post.post_id or not post.body:
            return False
        whitelisted = self._is_whitelisted_author(post.username, post.author_name)
        if (
            post.author_verified
            and self.config.skip_verified_authors
            and not whitelisted
        ):
            return False
        if self.config.skip_ai_content and post.is_ai:
            return False
        if len(post.body) < self.config.min_content_chars:
            return False
        if len(post.body) > self.config.max_content_chars:
            return False
        if post.view_count < self.config.min_view_count:
            return False
        return True

    def _similarity_threshold_for(self, post: SquareHotPost) -> float:
        if self._is_whitelisted_author(post.username, post.author_name):
            return float(self.config.official_similarity_threshold)
        return float(self.config.similarity_threshold)

    def _to_item(self, post: SquareHotPost) -> TweetSourceItem:
        is_long = (
            post.content_type == 2 and post.title and len(post.body) >= 800
        )
        post_type = "article" if is_long else "text"
        threshold = self._similarity_threshold_for(post)
        return TweetSourceItem(
            source_name="SquareHotSource",
            content_type="hot_rewrite",
            identifier=f"square-hot-{post.post_id}",
            title=post.title or post.body[:60],
            summary=post.body,
            body=post.body,
            post_type=post_type,
            coin_tags=post.coin_tags,
            metadata={
                "original_id": post.post_id,
                "original_author": post.author_name,
                "original_username": post.username,
                "original_author_verified": post.author_verified,
                "like_count": post.like_count,
                "view_count": post.view_count,
                "comment_count": post.comment_count,
                "share_count": post.share_count,
                "hashtags": post.hashtags,
                "is_ai": post.is_ai,
                "similarity_threshold": threshold,
            },
        )
