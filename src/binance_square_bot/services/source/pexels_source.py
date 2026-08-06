"""Pexels image-attribution service.

PexelsSource is NOT a content source. It is an image service that attaches
relevant free stock photos to real content items produced by other sources
(Fn news, Followin, BinanceAnn, SquareHot) before publishing:

  - article posts -> search one cover image by title/coin tags
  - text posts    -> convert to image post with 1-4 relevant images

The search query is derived from each item's own coin_tags and title, so
images match the actual content rather than a static keyword list.

Pexels API docs: https://www.pexels.com/api/documentation/
"""

from __future__ import annotations

import pathlib
import re
from typing import Any

import httpx
from loguru import logger
from pydantic import BaseModel

from binance_square_bot.services.base import BaseSource
from binance_square_bot.services.generation.models import TweetSourceItem

# Map Pexels response Content-Type to the extension we store/upload with.
# Binance media upload picks content-type from the file extension.
_EXT_BY_CONTENT_TYPE = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}

# Tokens too generic/ambiguous to make a good image search on their own.
_STOP_QUERY_TOKENS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "with",
    "is", "are", "was", "were", "be", "by", "as", "at", "it", "this", "that",
    "crypto", "cryptocurrency", "announcement", "update", "news", "post",
    "币安", "公告", "上线", "关于", "的", "与", "及", "或",
}


class PexelsPhoto(BaseModel):
    id: int
    width: int
    height: int
    url: str  # Pexels page (for attribution)
    photographer: str
    src_large: str
    src_original: str


class PexelsSource(BaseSource):
    """Attach Pexels images to content items. Not a content source itself."""

    class Config(BaseSource.Config):
        enabled: bool = False
        daily_max_executions: int = 1000  # not a source; limit is irrelevant
        api_key: str = ""
        api_url: str = "https://api.pexels.com/v1/search"
        # Number of images to attach to text posts (converted to image posts).
        text_post_images: int = 2
        # Article cover: always 1.
        min_width: int = 1024
        orientation: str = "landscape"  # landscape | portrait | square
        download_dir: str = "data/media/pexels"
        request_timeout: float = 20.0

    def __init__(self) -> None:
        super().__init__()
        self._client = httpx.Client(timeout=self.config.request_timeout)
        self._download_dir = pathlib.Path(self.config.download_dir)
        self._download_dir.mkdir(parents=True, exist_ok=True)

    # ----- BaseSource contract (no longer produces content) -----

    def fetch(self) -> list[Any]:
        return []

    def generate(self, data: Any) -> Any:
        return data

    # ----- image attribution -----

    def attach_images(self, items: list[TweetSourceItem]) -> int:
        """Mutate items in place, attaching relevant images.

        article posts get a cover; text posts are converted to image posts.
        Items that already have media, or for which no suitable image is
        found, are left untouched. Returns the number of items enriched.
        """
        if not self.config.api_key:
            logger.warning("Pexels API key not configured; skipping image attribution")
            return 0

        enriched = 0
        for item in items:
            # Don't override sources that already supply their own media.
            if item.images or item.cover or item.video:
                continue
            # Only text and article posts are good image candidates.
            if item.post_type not in ("text", "article"):
                continue
            try:
                if self._attach_one(item):
                    enriched += 1
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"Pexels attribution failed for {item.identifier}: {exc}")
        if enriched:
            logger.info(f"Pexels attached images to {enriched}/{len(items)} items")
        return enriched

    def _attach_one(self, item: TweetSourceItem) -> bool:
        query = self._build_query(item)
        if not query:
            return False

        wanted = 1 if item.post_type == "article" else self.config.text_post_images
        wanted = max(1, min(wanted, 4))
        photos = self._search(query, wanted)
        if not photos:
            return False

        paths: list[str] = []
        attribution: list[str] = []
        for photo in photos:
            local = self._download(photo)
            if local:
                paths.append(local)
                attribution.append(f"Photo by {photo.photographer} on Pexels ({photo.url})")
        if not paths:
            return False

        if item.post_type == "article":
            item.cover = paths[0]
        else:
            # text -> image post
            item.post_type = "image"
            item.images = paths[:4]

        existing = list(item.metadata.get("attribution", []))
        item.metadata["attribution"] = existing + attribution
        item.metadata["pexels_query"] = query
        return True

    # ----- internals -----

    def _search(self, query: str, wanted: int) -> list[PexelsPhoto]:
        params = {
            "query": query,
            "per_page": wanted + 2,
            "orientation": self.config.orientation,
        }
        response = self._client.get(
            self.config.api_url,
            headers={"Authorization": self.config.api_key},
            params=params,
        )
        response.raise_for_status()
        photos = self._parse_photos(response.json())
        photos = [p for p in photos if p.width >= self.config.min_width]
        return photos[:wanted]

    @staticmethod
    def _parse_photos(payload: dict) -> list[PexelsPhoto]:
        result: list[PexelsPhoto] = []
        for p in payload.get("photos", []):
            src = p.get("src", {})
            result.append(
                PexelsPhoto(
                    id=p["id"],
                    width=p.get("width", 0),
                    height=p.get("height", 0),
                    url=p.get("url", ""),
                    photographer=p.get("photographer", "Pexels"),
                    src_large=src.get("large") or src.get("large2x") or src.get("medium", ""),
                    src_original=src.get("original", ""),
                )
            )
        return result

    def _download(self, photo: PexelsPhoto) -> str | None:
        url = photo.src_original or photo.src_large
        if not url:
            return None
        # Default .jpg; corrected from Content-Type once the response arrives.
        target = self._download_dir / f"{photo.id}.jpg"
        try:
            with self._client.stream("GET", url) as resp:
                resp.raise_for_status()
                content_type = resp.headers.get("content-type", "").split(";")[0].lower()
                ext = _EXT_BY_CONTENT_TYPE.get(content_type, ".jpg")
                target = target.with_suffix(ext)
                if target.is_file() and target.stat().st_size > 0:
                    return str(target)
                with target.open("wb") as fh:
                    for chunk in resp.iter_bytes():
                        fh.write(chunk)
            return str(target)
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Pexels download failed for {photo.id}: {exc}")
            return None

    @staticmethod
    def _build_query(item: TweetSourceItem) -> str:
        """Derive an image-search query from the item's coin tags and title."""
        # Coin symbols make the most specific, relevant query.
        tokens: list[str] = list(dict.fromkeys(item.coin_tags))

        # Add meaningful words from the title (English/latin tokens only;
        # CJK titles don't search well on Pexels).
        if item.title:
            title_words = re.findall(r"[A-Za-z][A-Za-z0-9]+", item.title)
            for word in title_words:
                wl = word.lower()
                if wl not in _STOP_QUERY_TOKENS and word not in tokens:
                    tokens.append(word)

        # Pexels search works best with 1-3 terms.
        query = " ".join(tokens[:3]).strip()
        if not query:
            return "cryptocurrency"
        return query
