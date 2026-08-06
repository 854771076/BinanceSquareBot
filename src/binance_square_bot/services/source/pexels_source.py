"""Pexels image source.

Searches Pexels for free-to-use images, downloads them locally, and yields
TweetSourceItem objects with post_type='image' (or 'article' for Binance-
ecosystem keywords that benefit from long-form coverage).

Pexels API docs: https://www.pexels.com/api/documentation/
"""

from __future__ import annotations

import pathlib
from typing import Any

import httpx
from loguru import logger
from pydantic import BaseModel

from binance_square_bot.services.base import BaseSource
from binance_square_bot.services.generation.models import TweetSourceItem

# Keywords that signal Binance-platform relevance — these get long-form articles
# because Square boosts Binance-ecosystem content (per project guidance #2/#5).
BINANCE_KEYWORDS = {
    "binance",
    "bnb",
    "binance launchpool",
    "binance launchpad",
    "binance megadrop",
    "binance listing",
    "cz",
    "binance alpha",
}


class PexelsPhoto(BaseModel):
    id: int
    width: int
    height: int
    url: str  # Pexels page (for attribution)
    photographer: str
    photographer_url: str | None = None
    src_large: str
    src_original: str


class PexelsSearchResponse(BaseModel):
    photos: list[PexelsPhoto]
    total_results: int = 0


class PexelsSource(BaseSource):
    """Fetch images from Pexels and produce image/article TweetSourceItems."""

    class Config(BaseSource.Config):
        enabled: bool = False
        daily_max_executions: int = 1
        api_key: str = ""
        api_url: str = "https://api.pexels.com/v1/search"
        per_keyword: int = 3
        max_items_per_run: int = 10
        min_width: int = 1024
        orientation: str = "landscape"  # landscape | portrait | square
        download_dir: str = "data/media/pexels"
        keywords: list[str] = [
            "binance",
            "bitcoin",
            "ethereum",
            "cryptocurrency",
            "blockchain",
            "candlestick chart",
        ]

    def __init__(self) -> None:
        super().__init__()
        self._client = httpx.Client(timeout=30.0)
        self._download_dir = pathlib.Path(self.config.download_dir)
        self._download_dir.mkdir(parents=True, exist_ok=True)

    # ----- BaseSource contract -----

    def fetch(self) -> list[TweetSourceItem]:
        if not self.config.api_key:
            logger.warning("Pexels API key not configured; skipping")
            return []
        items: list[TweetSourceItem] = []
        for keyword in self.config.keywords:
            if len(items) >= self.config.max_items_per_run:
                break
            try:
                items.extend(self._fetch_keyword(keyword))
            except Exception as exc:  # noqa: BLE001
                logger.error(f"Pexels fetch failed for {keyword!r}: {exc}")
        return items[: self.config.max_items_per_run]

    def generate(self, data: Any) -> Any:
        # Pexels source maps directly to TweetSourceItem in fetch(); kept for API parity.
        return data

    # ----- internals -----

    def _fetch_keyword(self, keyword: str) -> list[TweetSourceItem]:
        headers = {"Authorization": self.config.api_key}
        params = {
            "query": keyword,
            "per_page": self.config.per_keyword + 2,  # fetch a few extras; width-filter below
            "orientation": self.config.orientation,
        }
        response = self._client.get(self.config.api_url, headers=headers, params=params)
        response.raise_for_status()
        payload = response.json()
        photos = self._parse_photos(payload)
        photos = [p for p in photos if p.width >= self.config.min_width]
        photos = photos[: self.config.per_keyword]
        if not photos:
            return []

        items: list[TweetSourceItem] = []
        downloaded: list[str] = []
        attribution: list[str] = []
        for photo in photos:
            local_path = self._download(photo)
            if not local_path:
                continue
            downloaded.append(local_path)
            attribution.append(f"Photo by {photo.photographer} on Pexels ({photo.url})")

        if not downloaded:
            return []

        is_binance = keyword.strip().lower() in BINANCE_KEYWORDS
        post_type = "article" if is_binance else "image"

        # For image posts cap at 4 images. For article covers use exactly 1.
        if post_type == "image":
            images = downloaded[:4]
            cover = None
        else:
            images = []
            cover = downloaded[0]

        item = TweetSourceItem(
            source_name=self.__class__.__name__,
            content_type="stock_image",
            identifier=f"pexels-{keyword}-{photos[0].id}",
            title=keyword,
            summary=(
                f"Pexels image set for keyword '{keyword}'. "
                "Write a Binance Square caption for these images."
            ),
            post_type=post_type,
            images=images,
            cover=cover,
            coin_tags=_coin_tags_for_keyword(keyword),
            metadata={
                "keyword": keyword,
                "attribution": attribution,
                "photo_ids": [p.id for p in photos[: len(downloaded)]],
            },
        )
        items.append(item)
        return items

    @staticmethod
    def _parse_photos(payload: dict) -> list[PexelsPhoto]:
        photos: list[PexelsPhoto] = []
        for p in payload.get("photos", []):
            src = p.get("src", {})
            photos.append(
                PexelsPhoto(
                    id=p["id"],
                    width=p.get("width", 0),
                    height=p.get("height", 0),
                    url=p.get("url", ""),
                    photographer=p.get("photographer", "Pexels"),
                    photographer_url=p.get("photographer_url"),
                    src_large=src.get("large") or src.get("large2x") or src.get("medium", ""),
                    src_original=src.get("original", ""),
                )
            )
        return photos

    def _download(self, photo: PexelsPhoto) -> str | None:
        target = self._download_dir / f"{photo.id}.jpg"
        if target.is_file() and target.stat().st_size > 0:
            return str(target)
        url = photo.src_original or photo.src_large
        if not url:
            return None
        try:
            with self._client.stream("GET", url) as resp:
                resp.raise_for_status()
                with target.open("wb") as fh:
                    for chunk in resp.iter_bytes():
                        fh.write(chunk)
            return str(target)
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Pexels download failed for {photo.id}: {exc}")
            return None


def _coin_tags_for_keyword(keyword: str) -> list[str]:
    """Map a Pexels search keyword to Binance-recognized coin symbols.

    Only returns symbols the keyword clearly implies — no guessing.
    """
    k = keyword.lower()
    if "bnb" in k or "binance" in k:
        return ["BNB"]
    if "bitcoin" in k or "btc" in k:
        return ["BTC"]
    if "ethereum" in k or "eth" in k:
        return ["ETH"]
    return []
