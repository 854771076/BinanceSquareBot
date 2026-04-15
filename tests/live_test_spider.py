"""
@file live_test_spider.py
@description 爬虫真实API调用测试（手动运行）
@usage python -m tests.live_test_spider
"""

import sys
from src.binance_square_bot.services.spider import FnSpiderService


def live_test() -> None:
    """真实调用API测试爬虫"""
    print("== ForesightNews Spider Live Test ==\n")

    spider = FnSpiderService()

    try:
        articles = spider.fetch_news_list()

        print(f"[OK] Request success! Got {len(articles)} articles\n")

        if not articles:
            print("[INFO] No important news today")
            return

        # 打印前5篇文章信息
        for i, article in enumerate(articles[:5], 1):
            print("=" * 60)
            print(f"Article #{i}")
            print(f"Title: {article.title}")
            print(f"URL: {article.url}")
            print(f"Time: {article.published_at}")
            content_preview = article.content
            print(f"Preview: {content_preview}")
            print()

        if len(articles) > 5:
            print(f"... and {len(articles) - 5} more articles not shown\n")

        print("[OK] Spider test completed successfully!")

    except Exception as e:
        print(f"[FAILED] Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    live_test()
