"""
@file spider.py
@description ForesightNews新闻API爬取服务
@design-doc docs/01-architecture/system-architecture.md
@task-id BE-06
@created-by fullstack-dev-workflow
"""

import base64
import zlib
import json
from datetime import datetime
from typing import List, Dict, Any

from curl_cffi import requests

from ..models.article import Article


class FnSpiderService:
    """ForesightNews新闻API客户端"""

    def __init__(self) -> None:
        self.base_url = "https://api.foresightnews.pro"
        self.session: requests.Session[requests.Response] = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36',
            'Referer': 'https://foresightnews.pro/',
            'Origin': 'https://foresightnews.pro',
            'Accept': 'application/json, text/plain, */*',
        })

    def _decompress_data(self, compressed_data: str) -> Dict[str, Any]:
        """解压缩API返回的数据"""
        # 补全padding
        padding = 4 - len(compressed_data) % 4
        if padding:
            compressed_data += '=' * padding

        # base64解码
        decoded = base64.b64decode(compressed_data)

        # zlib解压
        decompressed = zlib.decompress(decoded)

        # 解析JSON
        result: Dict[str, Any] = json.loads(decompressed.decode('utf-8'))
        return result

    def fetch_news_list(self) -> List[Article]:
        """获取今日重要新闻列表

        Returns:
            新闻文章列表
        """
        date_str = datetime.now().date().strftime("%Y%m%d")
        url = f"{self.base_url}/v1/dayNews?is_important=true&date={date_str}"

        resp = self.session.get(url, impersonate='chrome')
        resp.raise_for_status()
        data = resp.json()

        # 解压缩数据
        if data.get('code') == 1 and isinstance(data.get('data'), str):
            decompressed = self._decompress_data(data['data'])
        else:
            decompressed = data.get('data', {})

        articles: List[Article] = []

        # dayNews API返回格式: json_data[0].get('news', [])
        if isinstance(decompressed, list) and len(decompressed) > 0:
            news_list = decompressed[0].get('news', [])
            for item in news_list:
                article = self._parse_article(item)
                if article:
                    articles.append(article)

        return articles

    def _parse_article(self, item: Dict[str, Any]) -> Article | None:
        """解析单篇文章"""
        try:
            article_id = item.get('id')
            title = item.get('title', '').strip()
            source_link = item.get('source_link') or item.get('source_url')
            brief = item.get('brief', '').strip()
            published_at_ts = item.get('published_at')

            # 如果没有链接但有id，构建链接
            if not source_link and article_id:
                source_link = f"https://foresightnews.pro/news/{article_id}"

            if not title or not source_link:
                return None

            # 解析发布时间
            published_at = None
            if published_at_ts:
                try:
                    published_at = datetime.fromtimestamp(published_at_ts)
                except (ValueError, TypeError):
                    pass

            # 使用brief作为内容，如果为空则用title
            content = brief if brief else title

            return Article(
                title=title,
                url=source_link,
                content=content,
                published_at=published_at,
            )
        except Exception:
            return None
