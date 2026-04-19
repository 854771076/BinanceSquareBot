"""
@file cli.py
@description CLI命令行入口，使用Typer构建
@design-doc docs/08-cli-design/command-spec.md
@task-id BE-10
@created-by fullstack-dev-workflow
"""

import time
from concurrent.futures import ThreadPoolExecutor

import typer
from rich.console import Console
from rich.table import Table

from binance_square_bot.models import PolymarketMarket, Tweet
from binance_square_bot.services import (
    BinancePublisher,
    ForesightNewsSpider,
    PolymarketFetcher,
    PolymarketFilter,
    ResearchGenerator,
    Storage,
    TweetGenerator,
)

from . import __version__
from .config import config

app = typer.Typer(
    name="binance-square-bot",
    help="BinanceSquareBot - 自动爬取Fn新闻生成币安广场推文",
    add_completion=False,
)

console = Console()

# Polymarket research subcommand group
polymarket_app = typer.Typer(
    help="Polymarket 投资研报生成功能",
    add_completion=False,
)
app.add_typer(polymarket_app, name="polymarket-research")


def version_callback(value: bool) -> None:
    if value:
        console.print(f"BinanceSquareBot v{__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool | None = typer.Option(
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


@app.command("run")
def run(
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="试运行模式：只爬取和生成，不实际发布",
    ),
    limit: int | None = typer.Option(
        None,
        "--limit",
        help="限制处理文章数量（用于测试）",
    ),
) -> None:
    """执行一次完整的爬取-生成-发布流程"""

    console.print("[bold blue]🚀 启动 BinanceSquareBot[/bold blue]")

    # 初始化服务
    storage = Storage()
    spider = ForesightNewsSpider()
    generator = TweetGenerator()
    publisher = BinancePublisher()

    # 爬取新闻
    console.print("[blue]📥 正在爬取Fn新闻列表...[/]")
    try:
        articles = spider.fetch_news_list()
    except Exception as e:
        console.print(f"[red]❌ 爬取失败: {str(e)}[/]")
        raise typer.Exit(code=1) from e

    console.print(f"✓ 爬取完成，共 {len(articles)} 篇文章")

    # 过滤去重
    new_articles = []
    for article in articles:
        if not storage.is_url_processed(article.url):
            new_articles.append(article)

    console.print(f"✓ 去重完成，{len(new_articles)} 篇新文章待处理")

    if len(new_articles) == 0:
        console.print("[green]✨ 没有新文章，退出[/]")
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

    # 获取API密钥
    api_keys = config.binance_api_keys
    if not api_keys:
        console.print("[red]❌ 未配置BINANCE_API_KEYS[/]")
        raise typer.Exit(code=1)

    from threading import Lock
    stats_lock = Lock()

    # 逐个处理新文章
    for article in new_articles:
        with stats_lock:
            total_attempted += 1
            console.print(f"\n🔄 [blue]处理文章: {article.title}[/]")

        # 生成推文
        tweet = generator.generate_tweet(article)

        if not tweet.validation_passed:
            errors = ", ".join(tweet.validation_errors)
            console.print(f"⚠️  [yellow]格式校验失败: {errors}[/]")
            continue

        generated_ok += 1
        console.print(f"✓ 推文生成成功 ({len(tweet.content)} 字符)")

        if dry_run:
            console.print("⚠️  [yellow]试运行模式，跳过发布[/]")
            storage.mark_url_processed(article.url, processed=False)
            continue

        # 发布到所有API密钥（遵守每日限制）
        results = publisher.publish_tweet(tweet)

        # 更新计数和统计
        for api_key_idx, (success, error_msg) in enumerate(results):
            api_key = api_keys[api_key_idx]

            # 检查是否已达到每日上限，不继续发布
            current_count = storage.get_today_publish_count(api_key)
            if current_count >= config.daily_max_posts:
                continue

            if success:
                published_ok += 1
                storage.increment_today_publish_count(api_key)
                console.print(f"✅ [green]发布成功 [API#{api_key_idx + 1}] ({current_count + 1}/{config.daily_max_posts})[/]")
                storage.mark_url_processed(article.url, processed=True)
            else:
                published_failed += 1
                console.print(f"❌ [red]发布失败 [API#{api_key_idx + 1}]: {error_msg}[/]")

        # 发布间隔限制
        if not dry_run and len(new_articles) > 1 and total_attempted < len(new_articles):
            time.sleep(config.publish_interval_seconds)

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


@app.command("clean")
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

    storage = Storage()
    storage.clean_all()
    console.print("[green]✅ 已清空所有已处理记录[/]")


@polymarket_app.command("run")
def polymarket_research_run(
    dry_run: bool = typer.Option(False, "--dry-run", help="只生成，不发布"),
) -> None:
    """生成并发布 Polymarket 投资研报推文。"""
    if not config.enable_polymarket:
        console.print("[red]❌ Polymarket 功能在配置中已禁用[/]")
        raise typer.Exit(1)

    if not config.binance_api_keys:
        console.print("[red]❌ 未配置BINANCE_API_KEYS[/]")
        raise typer.Exit(1)

    storage = Storage()
    fetcher = PolymarketFetcher()
    published_ids = storage.get_all_published_condition_ids()
    filterer = PolymarketFilter(published_ids=published_ids)
    publisher = BinancePublisher()

    console.print("[blue]🔍 正在获取 Polymarket 市场数据...[/]")
    markets = fetcher.fetch_all_simplified()
    console.print(f"✓ 获取完成，共 {len(markets)} 个市场")

    top_markets = filterer.select_best_markets(markets)
    if not top_markets:
        console.print("[yellow]✨ 没有符合条件的市场[/]")
        raise typer.Exit(0)

    console.print(f"✓ 选中 {len(top_markets)} 个市场:")
    for i, market in enumerate(top_markets, 1):
        console.print(f"  {i}. {market.question}")
        console.print(f"      YES 概率: {market.yes_price:.1%}, NO: {market.no_price:.1%}")
        console.print(f"      交易量: {market.volume:.0f} USDC")

    # Define worker function for parallel generation
    def generate_market_research(market: PolymarketMarket) -> tuple[PolymarketMarket, Tweet | None, str]:
        """Worker function for parallel generation."""
        generator = ResearchGenerator()
        tweet, error = generator.generate_with_retry(market)
        return (market, tweet, error)

    # Execute parallel generation with ThreadPoolExecutor
    console.print(f"\n[blue]⚡ 正在并发生成 {len(top_markets)} 个市场研报...[/blue]")
    successful_generations: list[tuple[PolymarketMarket, Tweet]] = []
    generation_errors = 0

    with ThreadPoolExecutor(max_workers=config.max_concurrent_generations) as executor:
        futures = [
            executor.submit(generate_market_research, market)
            for market in top_markets
        ]
        for future in futures:
            try:
                market, tweet, error = future.result()
            except Exception as e:
                # The entire future failed unexpectedly - count it as an error and continue
                console.print(f"[red]❌ 生成任务异常: {str(e)}[/red]")
                generation_errors += 1
                continue
            if tweet is None:
                console.print(f"[red]❌ 生成失败: {market.question} - {error}[/red]")
                generation_errors += 1
                continue
            console.print(f"\n[green]✅ 生成成功: {market.question} ({len(tweet.content)} 字符)[/]")
            console.print("-" * 60)
            console.print(tweet.content)
            console.print("-" * 60)
            successful_generations.append((market, tweet))

    console.print(f"\n[blue]📊 生成完成: {len(successful_generations)} 成功, {generation_errors} 失败[/blue]")

    if not successful_generations:
        console.print("[yellow]✨ 没有成功生成的研报，退出[/yellow]")
        raise typer.Exit(0)

    if dry_run:
        console.print(f"\n[yellow]🏁 试运行完成，成功生成 {len(successful_generations)} 个研报[/yellow]")
        raise typer.Exit(0)

    # Implement sequential publishing after generation
    total_success = 0
    total_attempts = 0

    for idx, (market, tweet) in enumerate(successful_generations, 1):
        console.print(f"\n[blue]📤 正在发布第 {idx}/{len(successful_generations)}: {market.question}[/blue]")
        results = publisher.publish_tweet(tweet)
        success_count = sum(1 for success, _ in results if success)
        total_success += success_count
        total_attempts += len(results)

        # Log result for each API key
        for api_idx, (success, error) in enumerate(results, 1):
            if success:
                console.print(f"  [green]✅ 账号 {api_idx}: 发布成功[/green]")
            else:
                console.print(f"  [red]❌ 账号 {api_idx}: 发布失败 - {error}[/red]")

        console.print(f"  本市场发布结果: {success_count}/{len(results)} 成功")

        # Mark as published
        storage.add_published_polymarket(market.condition_id, market.question)

        # Add delay between posts
        if idx < len(successful_generations) and not dry_run:
            delay = config.publish_interval_seconds * config.max_concurrent_accounts
            console.print(f"  等待 {delay:.1f} 秒后发布下一篇...")
            time.sleep(delay)

    console.print(f"\n[green]🏁 全部完成，总计发布 {total_success}/{total_attempts} 成功[/green]")


@polymarket_app.command("scan")
def polymarket_research_scan(
    top_n: int = typer.Option(5, "--top-n", help="显示前 N 个候选市场"),
) -> None:
    """查看当前筛选出的最佳市场，不生成不发布。"""
    if not config.enable_polymarket:
        console.print("[red]❌ Polymarket 功能在配置中已禁用[/]")
        raise typer.Exit(1)

    storage = Storage()
    fetcher = PolymarketFetcher()
    published_ids = storage.get_all_published_condition_ids()
    filterer = PolymarketFilter(published_ids=published_ids)

    console.print("[blue]🔍 正在获取 Polymarket 市场数据...[/]")
    markets = fetcher.fetch_all_simplified()
    candidates = filterer.filter_min_volume(markets)
    candidates = filterer.exclude_published(candidates)
    candidates.sort(key=lambda m: m.score(), reverse=True)

    console.print(f"\n[bold cyan]前 {min(top_n, len(candidates))} 个候选市场:[/bold cyan]\n")
    for i, market in enumerate(candidates[:top_n], 1):
        console.print(f"[bold]{i}. {market.question}[/]")
        console.print(f"   condition_id: {market.condition_id}")
        console.print(f"   YES: {market.yes_price:.1%}, NO: {market.no_price:.1%}")
        console.print(f"   交易量: {market.volume:.0f}, 评分: {market.score():.2f}")
        console.print(f"   极端概率: {'是' if market.is_probability_extreme() else '否'}")
        console.print("")

    console.print(f"总计候选市场: {len(candidates)} / {len(markets)}")


# Keep top-level polymarket-scan for backward compatibility
@app.command("polymarket-scan")
def polymarket_scan_compat(
    top_n: int = typer.Option(5, "--top-n", help="显示前 N 个候选市场"),
) -> None:
    """扫描 Polymarket 市场，展示热门候选（不生成不发布）。"""
    # Delegate to the subcommand implementation
    polymarket_research_scan(top_n)


if __name__ == "__main__":
    app()
