import base64
import json
import zlib
from datetime import datetime
from typing import Any, List
from curl_cffi import requests
from pydantic import BaseModel
from loguru import logger

from binance_square_bot.services.base import BaseSource


class Article(BaseModel):
    """Fn news article model."""
    title: str
    url: str
    content: str
    published_at: datetime | None = None


class FnSource(BaseSource):
    """Fn news data source - crawls news and generates tweets."""

    Model = Article

    class Config(BaseSource.Config):
        base_url: str = "https://api.foresightnews.pro"
        timeout: int = 30
        daily_max_executions: int = 5

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36',
            'Referer': 'https://foresightnews.pro/',
            'Origin': 'https://foresightnews.pro',
            'Accept': 'application/json, text/plain, */*',
        })

    def _decompress_data(self, compressed_data: str) -> dict[str, Any]:
        """Decompress API response data."""
        padding = 4 - len(compressed_data) % 4
        if padding:
            compressed_data += '=' * padding

        decoded = base64.b64decode(compressed_data)
        decompressed = zlib.decompress(decoded)
        result: dict[str, Any] = json.loads(decompressed.decode('utf-8'))
        return result

    def fetch(self) -> List[Article]:
        """Fetch today's important news list."""
        date_str = datetime.now().date().strftime("%Y%m%d")
        url = f"{self.Config.model_fields['base_url'].default}/v1/dayNews?is_important=true&date={date_str}"

        resp = self.session.get(url, impersonate='chrome', timeout=self.Config.model_fields['timeout'].default)
        resp.raise_for_status()
        data = resp.json()

        # Decompress if needed
        if data.get('code') == 1 and isinstance(data.get('data'), str):
            decompressed = self._decompress_data(data['data'])
        else:
            decompressed = data.get('data', {})

        articles: List[Article] = []

        if isinstance(decompressed, list) and len(decompressed) > 0:
            news_list = decompressed[0].get('news', [])
            for item in news_list:
                article = self._parse_article(item)
                if article:
                    articles.append(article)

        logger.info(f"Fetched {len(articles)} articles from Fn news")
        return articles

    def _parse_article(self, item: dict[str, Any]) -> Article | None:
        """Parse single article item."""
        try:
            article_id = item.get('id')
            title = item.get('title', '').strip()
            source_link = item.get('source_link') or item.get('source_url')
            brief = item.get('brief', '').strip()
            published_at_ts = item.get('published_at')

            if not source_link and article_id:
                source_link = f"https://foresightnews.pro/news/{article_id}"

            if not title or not source_link:
                return None

            published_at = None
            if published_at_ts:
                try:
                    published_at = datetime.fromtimestamp(published_at_ts)
                except (ValueError, TypeError):
                    pass

            content = brief if brief else title

            return Article(
                title=title,
                url=source_link,
                content=content,
                published_at=published_at,
            )
        except Exception as e:
            logger.warning(f"Failed to parse article: {e}")
            return None

    def generate(self, articles: List[Article]) -> List[str]:
        """Generate tweet content from articles."""
        tweets = []
        for article in articles:
            # Simple generation - format article as tweet
            content = f"{article.title}\n\n{article.content}\n\n{article.url}"
            # Trim to reasonable length
            if len(content) > 280:
                content = content[:277] + "..."
            tweets.append(content)

        logger.info(f"Generated {len(tweets)} tweets from articles")
        return tweets
