# 限流发布功能设计文档

**日期：** 2026-04-22
**作者：** Claude Code
**状态：** 待实现

## 背景

当前 BinanceSquareBot 通过 GitHub Action 每小时运行一次，所有启用的来源（Fn新闻、日历、空投、募资、Followin各板块）会同时生成文章并一次性发布，导致发布行为过于集中，不像是真人操作。

## 目标

- ✅ 避免一次性发布大量文章
- ✅ 每个来源可以独立控制每次运行的生成数量
- ✅ 总发布量可控且可配置
- ✅ 改动最小，复用现有架构
- ✅ 新增：按天去重（当天发布过的URL/ID不再重复生成和发布）

## 设计方案

采用 **方案一：每批次发布上限 + 来源独立配额**

### 架构图

```
GitHub Action (cron: 每小时运行)
    ↓
ParallelCliService
    ├─ 来源层限流：每个source每次运行只生成N篇
    │   ├─ FnSource (新闻): limit=2
    │   ├─ FnSource (日历): limit=1
    │   ├─ FnSource (空投): limit=1
    │   ├─ FnSource (募资): limit=1
    │   ├─ FollowinSource (topics): limit=1
    │   ├─ FollowinSource (io-flow): limit=1
    │   └─ FollowinSource (discussion): limit=1
    ↓
所有生成的tweets汇总 (理论最大8篇)
    ↓
发布层限流：随机挑选N篇发布 (默认6篇)
    ↓
BinanceTarget 并发发布
```

## 详细实现

### 1. CLI 参数新增 (`src/binance_square_bot/cli.py`)

在 `parallel` 命令中新增参数：

```python
@app.command("parallel")
def parallel_run(
    # ... 现有参数
    total_per_run: int = typer.Option(6, "--total-per-run", "-t", help="Max total articles to publish per run"),
) -> None:
    service = ParallelCliService(
        # ... 现有参数
        total_per_run=total_per_run,
    )
    service.execute_all()
```

### 2. ParallelCliService 修改 (`src/binance_square_bot/services/cli/parallel_cli.py`)

```python
class ParallelCliService:
    def __init__(
        self,
        # ... 现有参数
        total_per_run: int = 6,
    ):
        # ... 现有代码
        self.total_per_run = total_per_run

    def execute_all(self) -> Dict[str, Any]:
        # ... 现有代码

        # 给每个source配置默认limit
        source_limits = {
            "FnSource_execute": 2,          # Fn新闻
            "FnSource_execute_calendar": 1,  # Fn日历
            "FnSource_execute_airdrops": 1,  # Fn空投
            "FnSource_execute_fundraising": 1,  # Fn募资
            "FollowinSource_execute_topics": 1,   # Followin热点
            "FollowinSource_execute_io_flow": 1,  # Followin资金流
            "FollowinSource_execute_discussion": 1,  # Followin讨论币种
        }

        # 构建source_configs时传入limit
        source_configs.append({
            "source": FnSource(),
            "execute": "execute",
            "limit": source_limits["FnSource_execute"],
        })
        # ... 其他source同理
```

### 3. SourceOrchestrator 发布层限流 (`src/binance_square_bot/services/concurrent_executor.py`)

在发布之前随机挑选文章：

```python
class SourceOrchestrator:
    def __init__(self, max_workers: int = 4, total_per_run: int | None = None):
        self.max_workers = max_workers
        self.total_per_run = total_per_run

    def run_sources(
        self,
        # ... 现有参数
        total_per_run: int | None = None,
    ) -> Dict[str, Any]:
        # ... 执行所有sources ...

        # 汇总所有生成的tweets
        all_tweets: List[str] = []
        for result in source_results.values():
            if result.success:
                tweets = result.data.get("tweets_generated", [])
                if isinstance(tweets, list):
                    all_tweets.extend(tweets)

        # 新增：发布前随机限流
        effective_limit = total_per_run or self.total_per_run
        if effective_limit and len(all_tweets) > effective_limit:
            import random
            random.shuffle(all_tweets)
            all_tweets = all_tweets[:effective_limit]
            console.print(f"[blue]🎯 Randomly selected {effective_limit} tweets for publication (total generated: {len(all_tweets) + len(skipped)})[/blue]")

        # ... 继续发布逻辑 ...
```

### 4. 默认配置值

| Source类型 | 默认每次limit | 说明 |
|-----------|-------------|------|
| Fn新闻 | 2 | 最常更新的来源 |
| Fn日历 | 1 | 日历事件不需要太多 |
| Fn空投 | 1 | |
| Fn募资 | 1 | |
| Followin topics | 1 | 热点话题 |
| Followin IO-flow | 1 | 资金流异动 |
| Followin discussion | 1 | 讨论最多币种 |
| **合计** | **8** | 每小时理论最大生成量 |
| **发布上限** | **6** | 每小时实际发布上限 |

## 测试计划

### 单元测试
1. 测试来源层限流是否生效
2. 测试发布层随机选择逻辑
3. 测试 `total_per_run=0/None` 的边界情况
4. 测试内容去重：`is_content_published_today()` 和 `mark_content_published()`
5. 测试去重过滤逻辑

### 集成测试
1. dry-run 模式下验证限流效果
2. 验证日志输出正确显示限流和去重信息
3. 验证完整流程：fetch → 去重过滤 → 限流 → 发布 → 记录

---

## 新增功能：按天去重（ID/URL）

**需求：** 当天发布过的文章（通过URL或ID识别），不再生成和发布。

### 5.1 新增数据表 `published_content`

**文件：** `src/binance_square_bot/models/published_content.py`

```python
class PublishedContentModel(Base):
    __tablename__ = "published_content"

    content_hash = Column(String(64), primary_key=True)  # URL或ID的SHA256 hash
    source_name = Column(String(100), primary_key=True, index=True)  # FnSource, FollowinSource等
    content_type = Column(String(50), primary_key=True, index=True)   # news, calendar, airdrop, fundraising, topics, io_flow, discussion
    date = Column(String(20), primary_key=True, index=True)           # YYYY-MM-DD
    published_at = Column(DateTime)
```

- **复合主键：** (content_hash, source_name, content_type, date)
- 保证同一天、同一来源、同一类型的同一内容不会重复发布

### 5.2 StorageService 新增方法

**文件：** `src/binance_square_bot/services/storage.py:100-150`

```python
# ===== 内容去重 =====

def is_content_published_today(
    self,
    source_name: str,
    content_type: str,
    content_identifier: str,
) -> bool:
    """Check if content (URL or ID) was published today."""
    content_hash = hashlib.sha256(content_identifier.encode()).hexdigest()
    date = datetime.now().strftime("%Y-%m-%d")

    with Database.get_session() as session:
        exists = session.query(PublishedContentModel).filter(
            PublishedContentModel.content_hash == content_hash,
            PublishedContentModel.source_name == source_name,
            PublishedContentModel.content_type == content_type,
            PublishedContentModel.date == date,
        ).first()
        return exists is not None

def mark_content_published(
    self,
    source_name: str,
    content_type: str,
    content_identifier: str,
) -> None:
    """Mark content as published today."""
    content_hash = hashlib.sha256(content_identifier.encode()).hexdigest()
    date = datetime.now().strftime("%Y-%m-%d")

    with Database.get_session() as session:
        # Check if already exists
        exists = session.query(PublishedContentModel).filter(
            PublishedContentModel.content_hash == content_hash,
            PublishedContentModel.source_name == source_name,
            PublishedContentModel.content_type == content_type,
            PublishedContentModel.date == date,
        ).first()

        if exists:
            return

        record = PublishedContentModel(
            content_hash=content_hash,
            source_name=source_name,
            content_type=content_type,
            date=date,
            published_at=datetime.now(),
        )
        session.add(record)
        session.commit()
```

### 5.3 各Source层过滤

需要修改每个Source的CLI Service，在fetch后、生成前过滤：

**文件：** `src/binance_square_bot/services/cli/fn_cli.py`, `followin_cli.py`

例子（Fn新闻）：
```python
def execute(self) -> Dict[str, Any]:
    source = FnSource()
    articles = source.fetch_news()

    # 过滤掉当天已发布的
    filtered_articles = [
        a for a in articles
        if not self.storage.is_content_published_today("FnSource", "news", a.url)
    ]
    logger.info(f"Filtered out {len(articles) - len(filtered_articles)} already published articles")

    # 应用limit限制
    if self.limit:
        filtered_articles = filtered_articles[:self.limit]

    # ... 继续生成逻辑 ...
```

### 5.4 发布成功后记录

**文件：** `src/binance_square_bot/services/concurrent_executor.py:150-240`

在 `SourceParallelPublisher.publish_to_targets()` 中，发布成功后记录。

**注意：** 因为当前的tweet只是纯文本，没有保留原始URL/ID信息，我们需要修改数据结构，让tweet携带identifier元数据：

```python
# 修改：从 List[str] 改为 List[Dict[str, str]]
# 每个tweet变成: {"text": "内容", "identifier": "url_or_id", "source_name": "...", "content_type": "..."}
```

---

## 向后兼容性

- 所有新增参数都有默认值，现有配置和调用方式完全不受影响
- 新增数据库表会自动创建（`Base.metadata.create_all()`），无需手动执行SQL
- 不改变发布重试和错误处理逻辑

## 后续优化方向（可选）

如果发现token浪费严重，可以升级到：
- 方案二：发布队列系统（先进先出，不浪费生成的文章）
- 方案三：智能时间分散调度（文章安排在未来随机时间点发布）
