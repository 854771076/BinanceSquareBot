"""Binance official announcement source.

Fetches announcement lists from Binance's public bapi (catalogs: new listings,
activities, latest news, airdrops), pulls each article's body via the detail
endpoint, and produces TweetSourceItem objects for AI polishing.

The list endpoint only returns title/code — the detail endpoint carries the
body as a draft-JSON tree, so two requests per item are required.
"""

from __future__ import annotations

import pathlib
from concurrent.futures import ThreadPoolExecutor
from typing import Any
from urllib.parse import urlparse

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
    cover: str | None = None  # local path to downloaded real cover image


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
        # Directory for real announcement cover images downloaded from bnbstatic.
        cover_dir: str = "data/media/binance-ann"
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

        # Fetch details concurrently — each is an independent HTTP round-trip
        # (plus a cover-image download). Fetch a few extra to absorb skips.
        target_count = self.config.max_items_per_run
        wanted = min(len(articles), target_count + 4)
        details: list[Announcement | None] = []
        with ThreadPoolExecutor(max_workers=min(6, wanted or 1)) as pool:
            for detail in pool.map(self._safe_fetch_detail, articles[:wanted]):
                details.append(detail)

        items: list[TweetSourceItem] = []
        for detail in details:
            if detail is None:
                continue
            item = self._to_item(detail)
            if item is not None:
                items.append(item)
                if len(items) >= target_count:
                    break
        return items

    def _safe_fetch_detail(self, article: Announcement) -> Announcement | None:
        try:
            return self._fetch_detail(article)
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"BinanceAnn detail failed for {article.code}: {exc}")
            return None

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
        body_tree = data.get("body")
        body_text = self._extract_body_text(body_tree)
        if not (self.config.min_body_chars <= len(body_text) <= self.config.max_body_chars):
            return None

        article.body = body_text
        article.catalog_name = data.get("firstCatalogName") or article.catalog_name
        article.coin_tags = _extract_coin_tags(data.get("pairs"))

        # Use the announcement's own first image as the real cover. Pexels
        # image-attribution skips items that already have a cover, so real
        # announcement art is never replaced with stock photos.
        image_url = self._extract_first_image_url(body_tree)
        if image_url:
            article.cover = self._download_cover(image_url, article.code)
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
        """Build a TweetSourceItem for the announcement.

        New-listing/long bodies become articles (Square boosts platform
        content). If the announcement carries its own image we download it as
        the real cover and Pexels image-attribution will leave it untouched
        (items that already have a cover are skipped). If it has no image we
        still emit an article with cover=None; the central Pexels service
        fills in a relevant stock cover. If neither succeeds the publisher's
        validate_media guard skips the item.
        """
        is_listing = article.catalog_id == 48
        body_len = len(article.body)
        post_type = "article" if (is_listing or body_len >= 800) else "text"
        return TweetSourceItem(
            source_name=self.__class__.__name__,
            content_type="announcement",
            identifier=f"binance-ann-{article.code}",
            title=article.title,
            summary=article.body[:300],
            body=article.body,
            url=f"{DETAIL_PAGE}/{article.code}",
            post_type=post_type,
            cover=article.cover,
            coin_tags=article.coin_tags,
            metadata={
                "code": article.code,
                "catalog_id": article.catalog_id,
                "catalog_name": article.catalog_name,
                "release_date": article.release_date,
            },
        )

    @staticmethod
    def _extract_first_image_url(body_tree: Any) -> str | None:
        """Walk the draft-JSON tree and return the first <img> src."""
        if not body_tree:
            return None
        if isinstance(body_tree, str):
            try:
                import json

                body_tree = json.loads(body_tree)
            except (ValueError, TypeError):
                return None

        found: list[str] = []

        def walk(node: Any) -> None:
            if found:
                return
            if isinstance(node, list):
                for n in node:
                    walk(n)
                return
            if not isinstance(node, dict):
                return
            if node.get("tag") == "img":
                src = (node.get("attr") or {}).get("src", "")
                if src and src.startswith("http"):
                    found.append(src)
                    return
            for child in node.get("child") or []:
                walk(child)

        walk(body_tree)
        return found[0] if found else None

    def _download_cover(self, url: str, code: str) -> str | None:
        """Download a real announcement cover image to a local file."""
        try:
            ext = pathlib.Path(urlparse(url).path).suffix or ".jpg"
            if ext.lower() not in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
                ext = ".jpg"
            cover_dir = pathlib.Path(self.config.cover_dir)
            cover_dir.mkdir(parents=True, exist_ok=True)
            target = cover_dir / f"{code}{ext}"
            if target.is_file() and target.stat().st_size > 0:
                return str(target)
            resp = self._client.get(url, timeout=self.config.request_timeout)
            resp.raise_for_status()
            target.write_bytes(resp.content)
            return str(target)
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"BinanceAnn cover download failed for {code}: {exc}")
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
