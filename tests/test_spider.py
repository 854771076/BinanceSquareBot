"""
@file test_spider.py
@description ForesightNews爬虫单元测试
@design-doc docs/01-architecture/system-architecture.md
@task-id BE-06
@created-by fullstack-dev-workflow
"""

import base64
import zlib
import json
from unittest.mock import Mock, patch
from datetime import datetime

from src.binance_square_bot.services.spider import FnSpiderService
from src.binance_square_bot.models.article import Article


def create_mock_decompress_data():
    """创建模拟压缩数据用于测试"""
    mock_data = [
        {
            "news": [
                {
                    "id": 12345,
                    "title": "比特币价格上涨",
                    "source_link": "https://example.com/news/1",
                    "brief": "比特币价格最近持续上涨，市场情绪乐观，美联储降息预期升温，资金流入加密市场。",
                    "published_at": int(datetime.now().timestamp()),
                },
                {
                    "id": 12346,
                    "title": "以太坊升级",
                    "source_link": "https://example.com/news/2",
                    "brief": "以太坊坎昆升级完成，性能提升，降低Gas费用。",
                    "published_at": int(datetime.now().timestamp()),
                }
            ]
        }
    ]
    json_str = json.dumps(mock_data)
    compressed = zlib.compress(json_str.encode('utf-8'))
    return base64.b64encode(compressed).decode('utf-8')


def test_decompress_data():
    """测试数据解压功能"""
    spider = FnSpiderService()

    # 测试解压
    test_data = create_mock_decompress_data()
    result = spider._decompress_data(test_data)

    assert isinstance(result, list)
    assert len(result) == 1
    assert 'news' in result[0]
    assert len(result[0]['news']) == 2


def test_parse_article():
    """测试单篇文章解析"""
    spider = FnSpiderService()

    # 完整文章
    item = {
        "id": 12345,
        "title": "测试文章标题",
        "source_link": "https://example.com/news/123",
        "brief": "这是文章摘要内容",
        "published_at": int(datetime(2024, 1, 1, 12, 0, 0).timestamp()),
    }

    article = spider._parse_article(item)

    assert article is not None
    assert article.title == "测试文章标题"
    assert article.url == "https://example.com/news/123"
    assert article.content == "这是文章摘要内容"
    assert article.published_at == datetime(2024, 1, 1, 12, 0, 0)


def test_parse_article_missing_title():
    """测试缺失标题的文章"""
    spider = FnSpiderService()

    item = {
        "id": 12345,
        "source_link": "https://example.com/news/123",
        "brief": "这是文章摘要内容",
    }

    article = spider._parse_article(item)
    assert article is None


def test_parse_article_missing_url():
    """测试缺失链接但有id，会自动构建链接"""
    spider = FnSpiderService()

    item = {
        "id": 12345,
        "title": "测试文章标题",
        "brief": "这是文章摘要内容",
    }

    article = spider._parse_article(item)
    assert article is not None
    assert article.title == "测试文章标题"
    assert article.url == "https://foresightnews.pro/news/12345"
    assert article.content == "这是文章摘要内容"


def test_parse_article_empty_brief():
    """测试空摘要用标题替代"""
    spider = FnSpiderService()

    item = {
        "id": 12345,
        "title": "测试文章标题",
        "source_link": "https://example.com/news/123",
        "brief": "",
    }

    article = spider._parse_article(item)

    assert article is not None
    assert article.content == "测试文章标题"


def test_parse_article_invalid_timestamp():
    """测试无效时间戳处理"""
    spider = FnSpiderService()

    item = {
        "id": 12345,
        "title": "测试文章",
        "source_link": "https://example.com/news/123",
        "brief": "测试内容",
        "published_at": "not-a-timestamp",
    }

    article = spider._parse_article(item)

    assert article is not None
    assert article.published_at is None


def test_fetch_news_list_success():
    """测试获取新闻列表成功场景"""
    spider = FnSpiderService()

    mock_response = Mock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {
        "code": 1,
        "data": create_mock_decompress_data(),
    }

    with patch.object(spider.session, 'get', return_value=mock_response):
        articles = spider.fetch_news_list()

        assert len(articles) == 2
        assert all(isinstance(a, Article) for a in articles)
        assert articles[0].title == "比特币价格上涨"
        assert articles[1].title == "以太坊升级"


def test_fetch_news_list_empty():
    """测试空新闻列表"""
    spider = FnSpiderService()

    empty_data = [{"news": []}]
    json_str = json.dumps(empty_data)
    compressed = zlib.compress(json_str.encode('utf-8'))
    b64_data = base64.b64encode(compressed).decode('utf-8')

    mock_response = Mock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {
        "code": 1,
        "data": b64_data,
    }

    with patch.object(spider.session, 'get', return_value=mock_response):
        articles = spider.fetch_news_list()
        assert len(articles) == 0


def test_fetch_news_list_not_compressed():
    """测试非压缩数据响应处理"""
    spider = FnSpiderService()

    mock_response = Mock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {
        "code": 1,
        "data": [{"news": []}],
    }

    with patch.object(spider.session, 'get', return_value=mock_response):
        articles = spider.fetch_news_list()
        assert len(articles) == 0
