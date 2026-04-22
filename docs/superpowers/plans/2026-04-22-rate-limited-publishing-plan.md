# 限流发布 + 内容去重 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现每批次发布上限 + 来源独立配额 + 按天内容去重功能，避免一次性发布大量文章和重复发布

**Architecture:** 
- 新增数据模型记录已发布内容
- StorageService 新增去重检查和记录方法
- 各 Source CLI Service 增加去重过滤
- ParallelCliService 和 SourceOrchestrator 增加两层限流机制

**Tech Stack:** Python 3.11, SQLAlchemy, Typer, Pytest

---

## Task 1: 新增 PublishedContentModel 数据模型

**Files:**
- Create: `src/binance_square_bot/models/published_content.py`
- Modify: `src/binance_square_bot/models/__init__.py`
- Test: `tests/models/test_published_content.py`

- [ ] **Step 1: Write the failing test**

```python
from datetime import datetime
from binance_square_bot.models.published_content import PublishedContentModel
from binance_square_bot.models.base import Database

def test_published_content_model():
    """Test that PublishedContentModel can be created and queried."""
    Database.init(":memory:")
    
    # Test hash_key and today methods
    today = PublishedContentModel.today()
    assert isinstance(today, str)
    assert len(today) == 10  # YYYY-MM-DD
    
    content_hash = PublishedContentModel.hash_content("https://example.com/article/123")
    assert len(content_hash) == 64  # SHA256 hex
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/models/test_published_content.py -v`
Expected: FAIL with "No module named 'binance_square_bot.models.published_content'"

- [ ] **Step 3: Write minimal implementation**

```python
from sqlalchemy import Column, String, DateTime
from datetime import datetime
import hashlib
from .base import Base

class PublishedContentModel(Base):
    __tablename__ = "published_content"

    content_hash = Column(String(64), primary_key=True)
    source_name = Column(String(100), primary_key=True, index=True)
    content_type = Column(String(50), primary_key=True, index=True)
    date = Column(String(20), primary_key=True, index=True)
    published_at = Column(DateTime)

    @classmethod
    def today(cls) -> str:
        return datetime.now().strftime("%Y-%m-%d")

    @classmethod
    def hash_content(cls, content_identifier: str) -> str:
        """Hash URL or ID for indexing - returns full SHA256 hex."""
        return hashlib.sha256(content_identifier.encode()).hexdigest()
```

- [ ] **Step 4: Update models __init__.py**

```python
# 在 src/binance_square_bot/models/__init__.py 中添加:
from .published_content import PublishedContentModel

__all__ = [
    "DailyExecutionStatsModel",
    "DailyPublishStatsModel",
    "PublishedContentModel",
]
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/models/test_published_content.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/binance_square_bot/models/published_content.py src/binance_square_bot/models/__init__.py tests/models/test_published_content.py
git commit -m "feat: add PublishedContentModel for content deduplication"
```

---

## Task 2: StorageService 新增去重方法

**Files:**
- Modify: `src/binance_square_bot/services/storage.py:100-150`
- Test: `tests/services/test_storage.py`

- [ ] **Step 1: Write the failing test**

```python
from binance_square_bot.services.storage import StorageService

def test_content_deduplication():
    """Test content deduplication functionality."""
    storage = StorageService(db_path=":memory:")
    
    source_name = "FnSource"
    content_type = "news"
    url = "https://example.com/article/123"
    
    # Should not be published initially
    assert not storage.is_content_published_today(source_name, content_type, url)
    
    # Mark as published
    storage.mark_content_published(source_name, content_type, url)
    
    # Now should be published
    assert storage.is_content_published_today(source_name, content_type, url)
    
    # Different URL should not be published
    assert not storage.is_content_published_today(source_name, content_type, "https://other.com")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/services/test_storage.py::test_content_deduplication -v`
Expected: FAIL with "'StorageService' object has no attribute 'is_content_published_today'"

- [ ] **Step 3: Implement the methods in StorageService**

```python
# 在 src/binance_square_bot/services/storage.py 末尾添加:

    # ===== Content Deduplication =====

    def is_content_published_today(
        self,
        source_name: str,
        content_type: str,
        content_identifier: str,
    ) -> bool:
        """Check if content (URL or ID) was published today."""
        from binance_square_bot.models.published_content import PublishedContentModel
        
        content_hash = PublishedContentModel.hash_content(content_identifier)
        date = PublishedContentModel.today()

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
        from binance_square_bot.models.published_content import PublishedContentModel
        from datetime import datetime
        
        content_hash = PublishedContentModel.hash_content(content_identifier)
        date = PublishedContentModel.today()

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

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/services/test_storage.py::test_content_deduplication -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/binance_square_bot/services/storage.py tests/services/test_storage.py
git commit -m "feat: add content deduplication methods to StorageService"
```

---

## Task 3: 修改 FnCliService 添加去重过滤

**Files:**
- Modify: `src/binance_square_bot/services/cli/fn_cli.py`
- Test: `tests/services/cli/test_fn_cli.py`

- [ ] **Step 1: Write the failing test**

```python
def test_fn_cli_deduplication_filter():
    """Test that FnCliService filters out already published articles."""
    from binance_square_bot.services.cli.fn_cli import FnCliService
    from binance_square_bot.services.storage import StorageService
    
    storage = StorageService(db_path=":memory:")
    service = FnCliService(dry_run=True, limit=5)
    
    # Mark an article as published
    storage.mark_content_published("FnSource", "news", "https://example.com/already-published")
    
    # This should be filtered out
    assert storage.is_content_published_today("FnSource", "news", "https://example.com/already-published")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/services/cli/test_fn_cli.py::test_fn_cli_deduplication_filter -v`
Expected: (may pass if just testing storage, but we need to test the filtering logic)

- [ ] **Step 3: Modify FnCliService to add filtering**

在每个 execute 方法中，添加去重过滤：

```python
# execute() 方法 - Fn新闻
def execute(self) -> Dict[str, Any]:
    source = FnSource()
    articles = source.fetch_news()
    logger.info(f"Fetched {len(articles)} news articles")

    # 过滤掉当天已发布的
    filtered_articles = [
        a for a in articles
        if not self.storage.is_content_published_today("FnSource", "news", a.url)
    ]
    logger.info(f"Filtered out {len(articles) - len(filtered_articles)} already published articles")

    # 应用limit限制
    if self.limit:
        filtered_articles = filtered_articles[:self.limit]
        logger.info(f"Limited to {self.limit} articles per run")

    if not filtered_articles:
        logger.info("No articles to process after filtering/limiting")
        return {"items_fetched": len(articles), "tweets_generated": [], "published_success": 0}

    # 使用 filtered_articles 继续生成...
```

同理修改：
- `execute_calendar()` - content_type: "calendar"
- `execute_airdrops()` - content_type: "airdrop"
- `execute_fundraising()` - content_type: "fundraising"

- [ ] **Step 4: Run tests**

Run: `pytest tests/services/cli/test_fn_cli.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/binance_square_bot/services/cli/fn_cli.py tests/services/cli/test_fn_cli.py
git commit -m "feat: add content deduplication filtering to FnCliService"
```

---

## Task 4: 修改 FollowinCliService 添加去重过滤

**Files:**
- Modify: `src/binance_square_bot/services/cli/followin_cli.py`
- Test: `tests/services/cli/test_followin_cli.py`

- [ ] **Step 1: Write the failing test**

```python
def test_followin_cli_deduplication_filter():
    """Test that FollowinCliService filters out already published topics."""
    from binance_square_bot.services.cli.followin_cli import FollowinCliService
    from binance_square_bot.services.storage import StorageService
    
    storage = StorageService(db_path=":memory:")
    
    # Mark a topic as published
    storage.mark_content_published("FollowinSource", "topics", "topic-123")
    
    # This should be filtered out
    assert storage.is_content_published_today("FollowinSource", "topics", "topic-123")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/services/cli/test_followin_cli.py::test_followin_cli_deduplication_filter -v`
Expected: (may pass if testing storage only)

- [ ] **Step 3: Modify FollowinCliService to add filtering**

修改三个方法：
- `execute_topics()` - content_type: "topics"
- `execute_io_flow()` - content_type: "io_flow"
- `execute_discussion()` - content_type: "discussion"

每个方法都需要添加类似的过滤逻辑，根据 Followin 的 ID 字段进行去重。

- [ ] **Step 4: Run tests**

Run: `pytest tests/services/cli/test_followin_cli.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/binance_square_bot/services/cli/followin_cli.py tests/services/cli/test_followin_cli.py
git commit -m "feat: add content deduplication filtering to FollowinCliService"
```

---

## Task 5: ParallelCliService 添加来源层限流配置

**Files:**
- Modify: `src/binance_square_bot/services/cli/parallel_cli.py`
- Test: `tests/services/cli/test_parallel_cli.py`

- [ ] **Step 1: Write the failing test**

```python
def test_parallel_cli_source_limits():
    """Test that ParallelCliService applies per-source limits."""
    from binance_square_bot.services.cli.parallel_cli import ParallelCliService
    
    service = ParallelCliService(dry_run=True, total_per_run=6)
    
    # Check that default limits are set correctly
    assert hasattr(service, 'total_per_run')
    assert service.total_per_run == 6
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/services/cli/test_parallel_cli.py::test_parallel_cli_source_limits -v`
Expected: FAIL

- [ ] **Step 3: Implement the changes**

```python
class ParallelCliService:
    def __init__(
        self,
        dry_run: bool = False,
        max_workers: int = 4,
        enable_fn: bool = True,
        enable_fn_calendar: bool = True,
        enable_fn_airdrop: bool = True,
        enable_fn_fundraising: bool = True,
        enable_polymarket: bool = False,
        enable_followin_topics: bool = True,
        enable_followin_io_flow: bool = True,
        enable_followin_discussion: bool = True,
        total_per_run: int = 6,  # 新增参数
    ):
        # ... 现有代码 ...
        self.total_per_run = total_per_run
        
        # 给每个source配置默认limit
        self.source_limits = {
            "FnSource_execute": 2,          # Fn新闻
            "FnSource_execute_calendar": 1,  # Fn日历
            "FnSource_execute_airdrops": 1,  # Fn空投
            "FnSource_execute_fundraising": 1,  # Fn募资
            "FollowinSource_execute_topics": 1,   # Followin热点
            "FollowinSource_execute_io_flow": 1,  # Followin资金流
            "FollowinSource_execute_discussion": 1,  # Followin讨论币种
        }

    def execute_all(self) -> Dict[str, Any]:
        # ... 现有代码 ...
        
        # 构建 source_configs 时传入 limit
        if self.enable_fn:
            source_configs.append({
                "source": FnSource(),
                "execute": "execute",
                "limit": self.source_limits["FnSource_execute"],
            })
        
        # 其他 source 同理...
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/services/cli/test_parallel_cli.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/binance_square_bot/services/cli/parallel_cli.py tests/services/cli/test_parallel_cli.py
git commit -m "feat: add per-source limit configuration to ParallelCliService"
```

---

## Task 6: CLI 添加 total_per_run 参数

**Files:**
- Modify: `src/binance_square_bot/cli.py:198-225`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write the failing test**

```python
def test_cli_parallel_total_per_run():
    """Test that parallel command accepts --total-per-run parameter."""
    from typer.testing import CliRunner
    from binance_square_bot.cli import app
    
    runner = CliRunner()
    result = runner.invoke(app, ["parallel", "--help"])
    assert result.exit_code == 0
    assert "--total-per-run" in result.output
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli.py::test_cli_parallel_total_per_run -v`
Expected: FAIL

- [ ] **Step 3: Implement the changes**

```python
@app.command("parallel")
def parallel_run(
    dry_run: bool = typer.Option(False, "--dry-run", help="Only generate, no publishing"),
    max_workers: int = typer.Option(4, "--workers", "-w", help="Max concurrent workers"),
    disable_fn: bool = typer.Option(False, "--no-fn", help="Disable Fn news source"),
    disable_fn_calendar: bool = typer.Option(False, "--no-fn-calendar", help="Disable Fn calendar events"),
    disable_fn_airdrop: bool = typer.Option(False, "--no-fn-airdrop", help="Disable Fn airdrop events"),
    disable_fn_fundraising: bool = typer.Option(False, "--no-fn-fundraising", help="Disable Fn fundraising events"),
    enable_polymarket: bool = typer.Option(False, "--enable-polymarket", help="Enable Polymarket source"),
    disable_followin_topics: bool = typer.Option(False, "--no-followin-topics", help="Disable Followin topics"),
    disable_followin_io: bool = typer.Option(False, "--no-followin-io", help="Disable Followin IO flow"),
    disable_followin_discussion: bool = typer.Option(False, "--no-followin-discussion", help="Disable Followin discussion"),
    total_per_run: int = typer.Option(6, "--total-per-run", "-t", help="Max total articles to publish per run"),  # 新增
) -> None:
    """Run ALL sources in parallel and publish to ALL targets concurrently."""
    service = ParallelCliService(
        dry_run=dry_run,
        max_workers=max_workers,
        enable_fn=not disable_fn,
        enable_fn_calendar=not disable_fn_calendar,
        enable_fn_airdrop=not disable_fn_airdrop,
        enable_fn_fundraising=not disable_fn_fundraising,
        enable_polymarket=enable_polymarket,
        enable_followin_topics=not disable_followin_topics,
        enable_followin_io_flow=not disable_followin_io,
        enable_followin_discussion=not disable_followin_discussion,
        total_per_run=total_per_run,
    )
    service.execute_all()
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_cli.py::test_cli_parallel_total_per_run -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/binance_square_bot/cli.py tests/test_cli.py
git commit -m "feat: add --total-per-run CLI parameter for parallel command"
```

---

## Task 7: SourceOrchestrator 发布层随机限流

**Files:**
- Modify: `src/binance_square_bot/services/concurrent_executor.py:100-135`
- Test: `tests/services/test_concurrent_executor.py`

- [ ] **Step 1: Write the failing test**

```python
def test_source_orchestrator_random_selection():
    """Test that SourceOrchestrator randomly selects tweets up to limit."""
    from binance_square_bot.services.concurrent_executor import SourceOrchestrator
    
    orchestrator = SourceOrchestrator(max_workers=4, total_per_run=3)
    
    # Test that total_per_run is stored
    assert orchestrator.total_per_run == 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/services/test_concurrent_executor.py::test_source_orchestrator_random_selection -v`
Expected: FAIL

- [ ] **Step 3: Implement the changes**

```python
class SourceOrchestrator:
    def __init__(self, max_workers: int = 4, total_per_run: int | None = None):
        self.max_workers = max_workers
        self.total_per_run = total_per_run

    def run_sources(
        self,
        source_configs: List[Dict[str, Any]],
        targets: List[Any],
        api_keys_map: Dict[str, List[str]],
        storage: Any,
        dry_run: bool = False,
        total_per_run: int | None = None,
    ) -> Dict[str, Any]:
        # ... 执行所有 sources ...

        # 汇总所有生成的tweets
        all_tweets: List[str] = []
        for result in source_results.values():
            if result.success:
                tweets = result.data.get("tweets_generated", [])
                if isinstance(tweets, list):
                    all_tweets.extend(tweets)

        # 新增：发布前随机限流
        effective_limit = total_per_run or self.total_per_run
        total_generated = len(all_tweets)
        if effective_limit and len(all_tweets) > effective_limit:
            import random
            random.shuffle(all_tweets)
            all_tweets = all_tweets[:effective_limit]
            console.print(f"[blue]🎯 Randomly selected {effective_limit} tweets for publication (total generated: {total_generated})[/blue]")
            logger.info(f"Randomly selected {effective_limit} tweets out of {total_generated} generated")

        # ... 继续发布逻辑 ...
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/services/test_concurrent_executor.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/binance_square_bot/services/concurrent_executor.py tests/services/test_concurrent_executor.py
git commit -m "feat: add random tweet selection with per-run limit to SourceOrchestrator"
```

---

## Task 8: 发布成功后记录已发布内容

**Files:**
- Modify: `src/binance_square_bot/services/concurrent_executor.py:150-240`
- Test: `tests/services/test_concurrent_executor.py`

**注意：** 这部分比较复杂，因为当前tweet只是纯文本，没有保留原始URL/ID信息。我们需要修改数据结构，让每个来源返回的tweet携带identifier元数据。

- [ ] **Step 1: 决定数据结构方案并实现**
- [ ] **Step 2: 修改各 Source 返回的 tweets 格式（携带 identifier）**
- [ ] **Step 3: 在发布成功后调用 mark_content_published**
- [ ] **Step 4: Run tests**
- [ ] **Step 5: Commit**

---

## Task 9: 完整集成测试

**Files:**
- Test: `tests/test_integration.py` (可能需要创建)

- [ ] **Step 1: Run dry-run integration test**
- [ ] **Step 2: Verify logs show filtering and limiting**
- [ ] **Step 3: Full test suite pass**
- [ ] **Step 4: Commit**

---

## 最终检查

- [ ] 所有测试通过: `pytest`
- [ ] 代码风格检查: `flake8` 或 `black --check`
- [ ] 手动测试: `poetry run binance-square-bot parallel --dry-run`
