"""
@file cli.py
@description CLI命令行入口，使用Typer构建
@design-doc docs/08-cli-design/command-spec.md
@task-id BE-10
@created-by fullstack-dev-workflow
"""

from typing import Optional
import typer
from rich.console import Console
from rich.table import Table
from datetime import datetime

from . import __version__
from .config import config
from .services.spider import FnSpiderService
from .services.storage import StorageService
from .services.generator import TweetGenerator
from .services.publisher import PublisherService, PublishResult


app = typer.Typer(
    name="binance-square-bot",
    help="BinanceSquareBot - 自动爬取Fn新闻生成币安广场推文",
    add_completion=False,
)

console = Console()


def version_callback(value: bool) -> None:
    if value:
        console.print(f"BinanceSquareBot v{__version__}")
        raise typer.Exit()


@app.callback()  # type: ignore[untyped-decorator]
def main(
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        "-v",
        help="显示版本号",
        callback=version_callback,
        is_eager=True,
    ),
) -> None:
    """BinanceSquareBot - 自动爬取Fn新闻生成币安广场推文"""
    pass


@app.command("run")  # type: ignore[untyped-decorator]
def run(
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="试运行模式：只爬取和生成，不实际发布",
    ),
    limit: Optional[int] = typer.Option(
        None,
        "--limit",
        help="限制处理文章数量（用于测试）",
    ),
) -> None:
    """执行一次完整的爬取-生成-发布流程"""

    console.print("[bold blue]🚀 启动 BinanceSquareBot[/bold blue]")

    # 初始化服务
    storage = StorageService()
    spider = FnSpiderService()
    generator = TweetGenerator()
    publisher = PublisherService()

    # 爬取新闻
    console.print("[blue]📥 正在爬取Fn新闻列表...[/blue]")
    try:
        articles = spider.fetch_news_list()
    except Exception as e:
        console.print(f"[red]❌ 爬取失败: {str(e)}[/red]")
        raise typer.Exit(code=1)

    console.print(f"✓ 爬取完成，共 {len(articles)} 篇文章")

    # 过滤去重
    new_articles = []
    for article in articles:
        if not storage.is_url_processed(article.url):
            new_articles.append(article)

    console.print(f"✓ 去重完成，{len(new_articles)} 篇新文章待处理")

    if len(new_articles) == 0:
        console.print("[green]✨ 没有新文章，退出[/green]")
        raise typer.Exit()

    # 限制处理数量
    if limit is not None and len(new_articles) > limit:
        console.print(f"⚠️  限制处理数量: {limit}")
        new_articles = new_articles[:limit]

    # 统计
    total_attempted = 0
    generated_ok = 0
    published_ok = 0
    published_failed = 0

    # 遍历API密钥
    api_keys = config.binance_api_keys
    if not api_keys:
        console.print("[red]❌ 未配置BINANCE_API_KEYS[/red]")
        raise typer.Exit(code=1)

    for api_key_idx, api_key in enumerate(api_keys):
        for article in new_articles:
            total_attempted += 1
            console.print(f"\n[blue]🔄 处理文章: {article.title}[/blue]")

            # 生成推文
            tweet = generator.generate_tweet(article)

            if not tweet.validation_passed:
                errors = ", ".join(tweet.validation_errors)
                console.print(f"[yellow]⚠️  格式校验失败: {errors}[/yellow]")
                continue

            generated_ok += 1
            console.print(f"✓ 推文生成成功 ({len(tweet.content)} 字符)")

            if dry_run:
                console.print("[yellow]⚠️  试运行模式，跳过发布[/yellow]")
                storage.mark_url_processed(article.url, processed=False)
                continue

            # 发布
            result = publisher.publish_tweet(api_key, tweet)

            if result.success:
                published_ok += 1
                console.print(f"[green]✅ 发布成功: {result.tweet_url}[/green]")
                storage.mark_url_processed(article.url, processed=True)
            else:
                published_failed += 1
                console.print(f"[red]❌ 发布失败: {result.error_message}[/red]")

    # 输出统计
    console.print("\n[bold green]✨ 执行完成[/bold green]")

    table = Table(title="执行统计")
    table.add_column("指标", style="cyan")
    table.add_column("数量", style="magenta")
    table.add_row("爬取总文章", str(len(articles)))
    table.add_row("去重新文章", str(len(new_articles)))
    table.add_row("生成成功", str(generated_ok))
    table.add_row("发布成功", str(published_ok))
    table.add_row("发布失败", str(published_failed))
    console.print(table)


@app.command("clean")  # type: ignore[untyped-decorator]
def clean(
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="跳过确认，直接清空",
    ),
) -> None:
    """清空已处理URL数据库，重置去重记录"""

    if not yes:
        confirm = typer.confirm(
            "⚠️  确认要清空已处理URL数据库吗？此操作不可恢复。"
        )
        if not confirm:
            raise typer.Exit()

    storage = StorageService()
    storage.clean_all()
    console.print("[green]✅ 已清空所有已处理记录[/green]")


if __name__ == "__main__":
    app()
