# Polymarket 生成阶段并发实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 `polymarket_research_run` 命令添加生成阶段并发，使用 ThreadPoolExecutor 并行调用LLM API生成研报，减少总执行时间。

**Architecture:** 采用"并发生成 + 顺序发布"架构：获取并筛选市场后，使用线程池并行生成所有推文，收集成功结果后再按顺序逐个发布，保持原有发布间隔限制和API限流策略。每个线程创建独立的 `ResearchGenerator` 实例保证线程安全。

**Tech Stack:** Python `concurrent.futures.ThreadPoolExecutor`, SQLite（线程安全），现有LangChain LLM调用接口。

---

## 文件结构

| 文件 | 变更类型 | 说明 |
|------|----------|------|
| `src/binance_square_bot/config.py` | 修改 | 添加 `max_concurrent_generations` 配置项 |
| `src/binance_square_bot/cli.py` | 修改 | 重构 `polymarket_research_run` 函数实现并发生成 |

---

### Task 1: 添加并发配置项

**Files:**
- Modify: `src/binance_square_bot/config.py:45-46`

- [ ] **Step 1: Add configuration field**

在 `Config` 类的发布限制部分添加新配置项：

```python
# 发布限制
daily_max_posts: int = 100
publish_interval_seconds: float = 1.0  # 单账号连续两篇推文发布间隔（秒）
max_concurrent_accounts: int = 3  # 最大并发账号数
max_concurrent_generations: int = 3  # 最大并发生成数（Polymarket研报生成）
```

- [ ] **Step 2: Commit**

```bash
git add src/binance_square_bot/config.py
git commit -m "feat: add max_concurrent_generations config for polymarket"
```

---

### Task 2: 重构 polymarket_research_run 实现并发生成

**Files:**
- Modify: `src/binance_square_bot/cli.py:215-294`

- [ ] **Step 1: Import ThreadPoolExecutor**

在文件顶部导入：

```python
from concurrent.futures import ThreadPoolExecutor
```

- [ ] **Step 2: Define worker function for parallel generation**

在 `polymarket_research_run` 函数内，筛选出 `top_markets` 后，定义生成工作函数：

```python
def generate_market_research(market: PolymarketMarket) -> tuple[PolymarketMarket, Tweet | None, str]:
    """Worker function for parallel generation."""
    generator = ResearchGenerator()
    tweet, error = generator.generate_with_retry(market)
    return (market, tweet, error)
```

- [ ] **Step 3: Execute parallel generation with ThreadPoolExecutor**

替换原有的顺序生成+发布循环：

```python
console.print(f"\n[blue]⚡ 正在并发生成 {len(top_markets)} 个市场研报...[/blue]")
successful_generations: list[tuple[PolymarketMarket, Tweet]] = []
generation_errors = 0

with ThreadPoolExecutor(max_workers=config.max_concurrent_generations) as executor:
    futures = [
        executor.submit(generate_market_research, market)
        for market in top_markets
    ]
    for future in futures:
        market, tweet, error = future.result()
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
```

- [ ] **Step 4: Implement sequential publishing after generation**

添加顺序发布循环：

```python
total_success = 0
total_attempts = 0

for idx, (market, tweet) in enumerate(successful_generations, 1):
    console.print(f"\n[blue]📤 正在发布第 {idx}/{len(successful_generations)}: {market.question}[/blue]")
    results = publisher.publish_tweet(tweet)
    success_count = sum(1 for success, _ in results if success)
    total_success += success_count
    total_attempts += len(results)

    # Mark as published
    storage.add_published_polymarket(market.condition_id, market.question)

    # Add delay between posts
    if idx < len(successful_generations) and not dry_run:
        time.sleep(config.publish_interval_seconds * config.max_concurrent_accounts)

console.print(f"\n[green]🏁 全部完成，总计发布 {total_success}/{total_attempts} 成功[/green]")
```

- [ ] **Step 5: Verify the full function structure is correct**

完整的 `polymarket_research_run` 函数结构应该是：

```python
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

    if dry_run:
        console.print("\n[yellow]⚠️  试运行模式，只生成不发布[/yellow]")

    # Parallel generation
    def generate_market_research(market: PolymarketMarket) -> tuple[PolymarketMarket, Tweet | None, str]:
        generator = ResearchGenerator()
        tweet, error = generator.generate_with_retry(market)
        return (market, tweet, error)

    console.print(f"\n[blue]⚡ 正在并发生成 {len(top_markets)} 个市场研报...[/blue]")
    successful_generations: list[tuple[PolymarketMarket, Tweet]] = []
    generation_errors = 0

    with ThreadPoolExecutor(max_workers=config.max_concurrent_generations) as executor:
        futures = [executor.submit(generate_market_research, market) for market in top_markets]
        for future in futures:
            market, tweet, error = future.result()
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

    # Sequential publishing
    publisher = BinancePublisher()
    total_success = 0
    total_attempts = 0

    for idx, (market, tweet) in enumerate(successful_generations, 1):
        console.print(f"\n[blue]📤 正在发布第 {idx}/{len(successful_generations)}: {market.question}[/blue]")
        results = publisher.publish_tweet(tweet)
        success_count = sum(1 for success, _ in results if success)
        total_success += success_count
        total_attempts += len(results)

        # Mark as published
        storage.add_published_polymarket(market.condition_id, market.question)

        # Add delay between posts
        if idx < len(successful_generations):
            time.sleep(config.publish_interval_seconds * config.max_concurrent_accounts)

    console.print(f"\n[green]🏁 全部完成，总计发布 {total_success}/{total_attempts} 成功[/green]")
```

- [ ] **Step 6: Test dry-run mode works correctly**

Run the command to verify imports and structure:

```bash
python -m binance_square_bot polymarket-research run --dry-run
```

Expected: Runs without syntax errors.

- [ ] **Step 7: Commit**

```bash
git add src/binance_square_bot/cli.py
git commit -m "feat: add concurrent generation for polymarket research run"
```

---

## Self-Review Checklist

1. **Spec coverage:** ✓ All requirements covered: add config, concurrent generation using ThreadPoolExecutor, sequential publishing, thread safety.
2. **Placeholder scan:** ✓ No placeholders, all code shown.
3. **Type consistency:** ✓ All names match existing code.

