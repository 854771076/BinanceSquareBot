"""Binance official announcement source.

Fetches announcement lists from Binance's public bapi (catalogs: new listings,
activities, latest news, airdrops), pulls each article's body via the detail
endpoint, and produces TweetSourceItem objects for AI polishing.

The list endpoint only returns title/code — the detail endpoint carries the
body as a draft-JSON tree, so two requests per item are required.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Any

from curl_cffi import requests
from loguru import logger
from pydantic import BaseModel

from binance_square_bot.services.base import BaseSource
from binance_square_bot.services.generation.models import TweetSourceItem

LIST_URL = "https://www.binance.com/bapi/apex/v1/public/apex/cms/article/list/query"
DETAIL_URL = "https://www.binance.com/bapi/composite/v1/public/cms/article/detail/query"
DETAIL_PAGE = "https://www.binance.com/zh-CN/support/announcement/detail"

# Block-level tags — a newline is emitted after walking their children so the
# extracted text keeps paragraph structure.
_BLOCK_TAGS = {"p", "li", "div", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "br"}


class Announcement(BaseModel):
    code: str
    title: str
    catalog_id: int
    catalog_name: str = ""
    body: str = ""
    coin_tags: list[str] = []
    release_date: int = 0


class BinanceAnnSource(BaseSource):
    """Fetch Binance official announcements for AI polishing."""

    class Config(BaseSource.Config):
        enabled: bool = False
        daily_max_executions: int = 3
        page_size: int = 10
        max_items_per_run: int = 5
        # 48 = 交易对上新, 93 = 活动, 49 = 最新动态, 128 = 空投
        catalogs: list[int] = [48, 93, 49, 128]
        min_body_chars: int = 80
        max_body_chars: int = 12000
        request_timeout: float = 15.0
        user_agent: str = (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
        )

    def __init__(self) -> None:
        super().__init__()
        self._client = requests.Session()
        self._client.headers.update(
            {
                "User-Agent": self.config.user_agent,
                "Accept": "application/json, text/plain, */*",
                "bnc-location": "CN",
                "lang": "zh-CN",
                "Referer": "https://www.binance.com/zh-CN/support/announcement",
            }
        )

    # ----- BaseSource contract -----

    def fetch(self) -> list[TweetSourceItem]:
        try:
            articles = self._fetch_all_lists()
        except Exception as exc:  # noqa: BLE001
            logger.error(f"BinanceAnn list fetch failed: {exc}")
            return []

        items: list[TweetSourceItem] = []
        for article in articles:
            if len(items) >= self.config.max_items_per_run:
                break
            try:
                detail = self._fetch_detail(article)
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"BinanceAnn detail failed for {article.code}: {exc}")
                continue
            if detail is None:
                continue
            item = self._to_item(detail)
            if item is not None:
                items.append(item)
        return items

    def generate(self, data: Any) -> Any:
        return data

    # ----- internals -----

    def _fetch_all_lists(self) -> list[Announcement]:
        """Fetch all catalogs concurrently, dedupe by code."""
        catalogs = self.config.catalogs
        with ThreadPoolExecutor(max_workers=min(4, len(catalogs)) or 1) as pool:
            results = list(pool.map(self._fetch_list, catalogs))

        seen: set[str] = set()
        articles: list[Announcement] = []
        for catalog_articles in results:
            for a in catalog_articles:
                if a.code and a.code not in seen:
                    seen.add(a.code)
                    articles.append(a)
        return articles

    def _fetch_list(self, catalog_id: int) -> list[Announcement]:
        params = {
            "type": 1,
            "pageNo": 1,
            "pageSize": self.config.page_size,
            "catalogId": catalog_id,
        }
        resp = self._client.get(
            LIST_URL,
            params=params,
            impersonate="chrome",
            timeout=self.config.request_timeout,
        )
        resp.raise_for_status()
        payload = resp.json()
        if str(payload.get("code")) not in ("000000", "0"):
            raise RuntimeError(f"list error: {payload.get('message')} ({payload.get('code')})")
        data = payload.get("data") or {}
        catalogs = data.get("catalogs") or []
        raw_articles = catalogs[0].get("articles", []) if catalogs else data.get("articles", [])
        catalog_name = ""
        if catalogs:
            catalog_name = catalogs[0].get("catalogName") or ""

        articles: list[Announcement] = []
        for raw in raw_articles:
            code = str(raw.get("code") or "")
            if not code:
                continue
            articles.append(
                Announcement(
                    code=code,
                    title=str(raw.get("title") or ""),
                    catalog_id=catalog_id,
                    catalog_name=catalog_name,
                    release_date=int(raw.get("releaseDate") or 0),
                )
            )
        return articles

    def _fetch_detail(self, article: Announcement) -> Announcement | None:
        resp = self._client.get(
            DETAIL_URL,
            params={"articleCode": article.code},
            impersonate="chrome",
            timeout=self.config.request_timeout,
        )
        resp.raise_for_status()
        payload = resp.json()
        if str(payload.get("code")) not in ("000000", "0"):
            logger.warning(f"detail error for {article.code}: {payload.get('message')}")
            return None
        data = payload.get("data") or {}
        body_text = self._extract_body_text(data.get("body"))
        if not (self.config.min_body_chars <= len(body_text) <= self.config.max_body_chars):
            return None

        article.body = body_text
        article.catalog_name = data.get("firstCatalogName") or article.catalog_name
        article.coin_tags = _extract_coin_tags(data.get("pairs"))
        return article

    @staticmethod
    def _extract_body_text(body: Any) -> str:
        """Walk the draft-JSON tree and concatenate text nodes.

        Text lives under nodes like {"node": "text", "text": "..."}; block
        elements get a trailing newline to preserve paragraph breaks.
        """
        if not body:
            return ""
        if isinstance(body, str):
            try:
                import json

                body = json.loads(body)
            except (ValueError, TypeError):
                return body.strip()

        parts: list[str] = []

        def walk(node: Any) -> None:
            if isinstance(node, list):
                for n in node:
                    walk(n)
                return
            if not isinstance(node, dict):
                return
            if node.get("node") == "text":
                text = node.get("text") or ""
                if text:
                    parts.append(text)
                return
            tag = node.get("tag")
            for child in node.get("child") or []:
                walk(child)
            if tag in _BLOCK_TAGS:
                parts.append("\n")

        walk(body)
        text = "".join(parts)
        # Collapse 3+ newlines into a blank line; strip trailing whitespace per line.
        lines = [line.strip() for line in text.splitlines()]
        return "\n".join(line for line in lines if line).strip()

    def _to_item(self, article: Announcement) -> TweetSourceItem | None:
        """Build a TweetSourceItem, or None if the announcement is unpublishable.

        New-listing/long bodies want an article (Square boosts platform content),
        but articles require a cover image. If no cover can be fetched (e.g. no
        Pexels key) the body is too long for the text-post limit, so we skip the
        item rather than emit something the validator will reject.
        """
        is_listing = article.catalog_id == 48
        body_len = len(article.body)
        wants_article = is_listing or body_len >= 800
        cover = self._fetch_cover(article) if wants_article else None
        if wants_article and not cover:
            logger.info(
                f"Skipping {article.code}: article needs a cover but none was "
                "fetched (set PEXELS_SOURCE_API_KEY to enable BinanceAnn articles)"
            )
            return None
        post_type = "article" if cover else "text"
        return TweetSourceItem(
            source_name=self.__class__.__name__,
            content_type="announcement",
            identifier=f"binance-ann-{article.code}",
            title=article.title,
            summary=article.body[:300],
            body=article.body,
            url=f"{DETAIL_PAGE}/{article.code}",
            post_type=post_type,
            cover=cover,
            coin_tags=article.coin_tags,
            metadata={
                "code": article.code,
                "catalog_id": article.catalog_id,
                "catalog_name": article.catalog_name,
                "release_date": article.release_date,
            },
        )

    def _fetch_cover(self, article: Announcement) -> str | None:
        """Fetch a generic crypto cover from Pexels if its API key is set.

        Returns None when Pexels is not configured or the download fails —
        the item then falls back to a text post instead of an article.
        """
        import os

        if not os.environ.get("PEXELS_SOURCE_API_KEY", "").strip():
            return None
        try:
            # Import lazily so this source works without Pexels enabled.
            from binance_square_bot.services.source.pexels_source import PexelsSource

            pexels = PexelsSource()
            keyword = "binance" if article.catalog_id == 48 else "cryptocurrency"
            resp = pexels._client.get(
                pexels.config.api_url,
                headers={"Authorization": pexels.config.api_key},
                params={"query": keyword, "per_page": 1, "orientation": "landscape"},
            )
            resp.raise_for_status()
            photos = pexels._parse_photos(resp.json())
            if not photos:
                return None
            return pexels._download(photos[0])
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"BinanceAnn cover fetch failed for {article.code}: {exc}")
            return None


# Quote assets Binance lists against — strip to get the base symbol for $tags.
_QUOTE_ASSETS = ("USDT", "FDUSD", "TUSD", "USDC", "BTC", "ETH", "BNB")


def _extract_coin_tags(pairs: Any) -> list[str]:
    """Extract base coin symbols from the detail endpoint's `pairs` field.

    Shape observed: [{"pair": "BTCUSDT", ...}] or list of strings. Empty most
    of the time — when empty we emit no tags rather than guessing.
    """
    if not pairs:
        return []
    tags: list[str] = []
    for p in pairs:
        if isinstance(p, dict):
            pair = str(p.get("pair") or p.get("symbol") or "").upper()
        elif isinstance(p, str):
            pair = p.upper()
        else:
            continue
        base = next((pair[: -len(q)] for q in _QUOTE_ASSETS if pair.endswith(q)), "")
        if base and base not in tags:
            tags.append(base)
    return tags
