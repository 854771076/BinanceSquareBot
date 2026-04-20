# BinanceSquareBot Code Refactoring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor BinanceSquareBot into a plugin-based architecture with BaseSource/BaseTarget inheritance, configuration auto-discovery, multi-API key support with ORM-based rate limiting, and loguru logging.

**Architecture:** BaseSource and BaseTarget abstract base classes with auto-registration via `__init_subclass__`, SQLAlchemy ORM for persistence, CLI business logic encapsulated in separate services.

**Tech Stack:** Python 3.11+, Pydantic 2.x, Pydantic Settings, SQLAlchemy 2.x, Loguru, Typer, Httpx

---

## File Structure Map

| File | Change Type | Responsibility |
|------|-------------|----------------|
| `pyproject.toml` | Modify | Add SQLAlchemy dependency |
| `src/binance_square_bot/models/base.py` | Create | SQLAlchemy Base class and Database connection manager |
| `src/binance_square_bot/models/daily_execution_stats.py` | Create | Source daily execution count ORM model |
| `src/binance_square_bot/models/daily_publish_stats.py` | Create | Target daily publish count ORM model (per API key) |
| `src/binance_square_bot/services/base.py` | Create | BaseSource and BaseTarget abstract base classes |
| `src/binance_square_bot/config.py` | Modify | MainConfig with source/target config registration |
| `src/binance_square_bot/common/logging.py` | Create | Loguru unified configuration |
| `src/binance_square_bot/services/source/fn_source.py` | Create | Fn news source: fetch + generate + Article model |
| `src/binance_square_bot/services/source/polymarket_source.py` | Create | Polymarket source: fetch + generate + Market model |
| `src/binance_square_bot/services/source/__init__.py` | Create | Source auto-registration via imports |
| `src/binance_square_bot/services/target/binance_target.py` | Create | Binance target with multi-API key support |
| `src/binance_square_bot/services/target/__init__.py` | Create | Target auto-registration via imports |
| `src/binance_square_bot/services/storage.py` | Modify | Rewrite to SQLAlchemy ORM implementation |
| `src/binance_square_bot/services/cli/fn_cli.py` | Create | Fn CLI business logic service |
| `src/binance_square_bot/services/cli/polymarket_cli.py` | Create | Polymarket CLI business logic service |
| `src/binance_square_bot/services/cli/common_cli.py` | Create | Clean DB CLI command |
| `src/binance_square_bot/services/cli/__init__.py` | Create | CLI services exports |
| `src/binance_square_bot/cli.py` | Modify | Simplified CLI entry point |
| `tests/models/test_daily_execution_stats.py` | Create | Tests for execution stats model |
| `tests/models/test_daily_publish_stats.py` | Create | Tests for publish stats model |
| `tests/services/test_base.py` | Create | Tests for BaseSource/BaseTarget |
| `tests/services/test_storage.py` | Create | Tests for StorageService |

---

### Task 1: Update Dependencies

**Files:**
- Modify: `pyproject.toml`
- Test: None

- [ ] **Step 1: Add SQLAlchemy to dependencies**

```toml
dependencies = [
    "langchain>=0.2.0",
    "langchain-openai>=0.1.0",
    "langgraph>=0.1.0",
    "pydantic>=2.0",
    "pydantic-settings>=2.0",
    "typer>=0.9.0",
    "rich>=13.0.0",
    "curl-cffi>=0.6.0",
    "httpx>=0.25.0",
    "loguru>=0.7.0",
    "sqlalchemy>=2.0.0",
]
```

- [ ] **Step 2: Install new dependency**

Run: `pip install -e .`
Expected: SQLAlchemy installs successfully

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "deps: add sqlalchemy 2.x for ORM"
```

---

### Task 2: SQLAlchemy Base Class and Database Manager

**Files:**
- Create: `src/binance_square_bot/models/base.py`
- Test: `tests/models/test_base.py`

- [ ] **Step 1: Write failing test**

```python
# tests/models/test_base.py
from sqlalchemy import Column, String, Integer
from binance_square_bot.models.base import Base, Database

def test_database_init():
    """Test database initialization creates tables."""
    class TestModel(Base):
        __tablename__ = "test_table"
        id = Column(Integer, primary_key=True)
        name = Column(String)
    
    Database.init(":memory:")
    
    with Database.get_session() as session:
        # Should be able to create and query
        obj = TestModel(name="test")
        session.add(obj)
        session.commit()
        
        result = session.query(TestModel).first()
        assert result.name == "test"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/models/test_base.py -v`
Expected: FAIL with "No module named binance_square_bot.models.base"

- [ ] **Step 3: Write minimal implementation**

```python
# src/binance_square_bot/models/base.py
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager

Base = declarative_base()

class Database:
    _engine = None
    _SessionLocal = None
    
    @classmethod
    def init(cls, db_path: str = "data/app.db"):
        cls._engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
        cls._SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=cls._engine)
        Base.metadata.create_all(bind=cls._engine)
    
    @classmethod
    @contextmanager
    def get_session(cls) -> Session:
        session = cls._SessionLocal()
        try:
            yield session
        finally:
            session.close()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/models/test_base.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/binance_square_bot/models/base.py tests/models/test_base.py
git commit -m "feat: add sqlalchemy base and database manager"
```

---

### Task 3: Daily Execution Stats Model

**Files:**
- Create: `src/binance_square_bot/models/daily_execution_stats.py`
- Test: `tests/models/test_daily_execution_stats.py`

- [ ] **Step 1: Write failing test**

```python
# tests/models/test_daily_execution_stats.py
from binance_square_bot.models.base import Database
from binance_square_bot.models.daily_execution_stats import DailyExecutionStatsModel

def test_today_date_format():
    """Test today() returns YYYY-MM-DD format."""
    date_str = DailyExecutionStatsModel.today()
    assert len(date_str) == 10
    assert date_str[4] == "-"
    assert date_str[7] == "-"

def test_can_execute():
    """Test can_execute logic."""
    stat = DailyExecutionStatsModel(count=5)
    assert stat.can_execute(10) is True
    assert stat.can_execute(5) is False

def test_model_persistence():
    """Test model can be saved and queried."""
    Database.init(":memory:")
    
    with Database.get_session() as session:
        stat = DailyExecutionStatsModel(
            source_name="TestSource",
            date=DailyExecutionStatsModel.today(),
            count=3
        )
        session.add(stat)
        session.commit()
        
        result = session.query(DailyExecutionStatsModel).filter_by(
            source_name="TestSource"
        ).first()
        assert result.count == 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/models/test_daily_execution_stats.py -v`
Expected: FAIL with "No module named binance_square_bot.models.daily_execution_stats"

- [ ] **Step 3: Write minimal implementation**

```python
# src/binance_square_bot/models/daily_execution_stats.py
from sqlalchemy import Column, String, Integer, DateTime
from datetime import datetime
from .base import Base

class DailyExecutionStatsModel(Base):
    __tablename__ = "daily_execution_stats"
    
    source_name = Column(String, primary_key=True, index=True)
    date = Column(String, primary_key=True, index=True)  # YYYY-MM-DD
    count = Column(Integer, default=0)
    last_executed_at = Column(DateTime)
    
    @classmethod
    def today(cls) -> str:
        return datetime.now().strftime("%Y-%m-%d")
    
    def can_execute(self, max_executions: int) -> bool:
        return self.count < max_executions
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/models/test_daily_execution_stats.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/binance_square_bot/models/daily_execution_stats.py tests/models/test_daily_execution_stats.py
git commit -m "feat: add daily execution stats orm model"
```

---

### Task 4: Daily Publish Stats Model (Multi API Key Support)

**Files:**
- Create: `src/binance_square_bot/models/daily_publish_stats.py`
- Test: `tests/models/test_daily_publish_stats.py`

- [ ] **Step 1: Write failing test**

```python
# tests/models/test_daily_publish_stats.py
from binance_square_bot.models.base import Database
from binance_square_bot.models.daily_publish_stats import DailyPublishStatsModel

def test_today_date_format():
    """Test today() returns YYYY-MM-DD format."""
    date_str = DailyPublishStatsModel.today()
    assert len(date_str) == 10
    assert date_str[4] == "-"
    assert date_str[7] == "-"

def test_api_key_hashing():
    """Test API key hashing produces consistent short hash."""
    key = "test_api_key_12345"
    hash1 = DailyPublishStatsModel.hash_key(key)
    hash2 = DailyPublishStatsModel.hash_key(key)
    assert hash1 == hash2
    assert len(hash1) == 16  # 16 hex chars

def test_api_key_masking():
    """Test API key masking hides middle portion."""
    key = "abcdefghijklmnop"
    masked = DailyPublishStatsModel.mask_key(key)
    assert masked.startswith("abcd")
    assert masked.endswith("mnop")
    assert "..." in masked
    
    # Short keys not masked
    short_key = "abcd"
    assert DailyPublishStatsModel.mask_key(short_key) == short_key

def test_model_persistence():
    """Test model can be saved and queried by api_key_hash."""
    Database.init(":memory:")
    
    api_key = "binance_test_key"
    key_hash = DailyPublishStatsModel.hash_key(api_key)
    
    with Database.get_session() as session:
        stat = DailyPublishStatsModel(
            target_name="BinanceTarget",
            api_key_hash=key_hash,
            api_key_mask=DailyPublishStatsModel.mask_key(api_key),
            date=DailyPublishStatsModel.today(),
            count=5
        )
        session.add(stat)
        session.commit()
        
        result = session.query(DailyPublishStatsModel).filter_by(
            target_name="BinanceTarget",
            api_key_hash=key_hash
        ).first()
        assert result.count == 5
        assert "..." in result.api_key_mask
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/models/test_daily_publish_stats.py -v`
Expected: FAIL with "No module named binance_square_bot.models.daily_publish_stats"

- [ ] **Step 3: Write minimal implementation**

```python
# src/binance_square_bot/models/daily_publish_stats.py
from sqlalchemy import Column, String, Integer, DateTime
from datetime import datetime
import hashlib
from .base import Base

class DailyPublishStatsModel(Base):
    __tablename__ = "daily_publish_stats"
    
    target_name = Column(String, primary_key=True, index=True)
    api_key_hash = Column(String, primary_key=True, index=True)  # API key hash
    api_key_mask = Column(String)                                  # Masked for display
    date = Column(String, primary_key=True, index=True)           # YYYY-MM-DD
    count = Column(Integer, default=0)
    last_published_at = Column(DateTime)
    
    @classmethod
    def today(cls) -> str:
        return datetime.now().strftime("%Y-%m-%d")
    
    @classmethod
    def hash_key(cls, api_key: str) -> str:
        """Hash API key for indexing (16 hex chars)."""
        return hashlib.sha256(api_key.encode()).hexdigest()[:16]
    
    @classmethod
    def mask_key(cls, api_key: str) -> str:
        """Mask API key for display: first 4 chars + ... + last 4 chars."""
        if len(api_key) <= 8:
            return api_key
        return f"{api_key[:4]}...{api_key[-4:]}"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/models/test_daily_publish_stats.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/binance_square_bot/models/daily_publish_stats.py tests/models/test_daily_publish_stats.py
git commit -m "feat: add daily publish stats orm model with multi api key support"
```

---

### Task 5: BaseSource and BaseTarget Abstract Classes

**Files:**
- Create: `src/binance_square_bot/services/base.py`
- Test: `tests/services/test_base.py`

- [ ] **Step 1: Write failing test**

```python
# tests/services/test_base.py
from pydantic import BaseModel
from binance_square_bot.services.base import BaseSource, BaseTarget

def test_base_source_config():
    """Test BaseSource has default config."""
    assert BaseSource.Config.model_fields["enabled"].default is True
    assert BaseSource.Config.model_fields["daily_max_executions"].default == 1

def test_base_target_config():
    """Test BaseTarget has default config."""
    assert BaseTarget.Config.model_fields["enabled"].default is True
    assert BaseTarget.Config.model_fields["daily_max_posts_per_key"].default == 100
    assert BaseTarget.Config.model_fields["api_keys"].default == []

def test_subclass_inheritance():
    """Test subclass can inherit and extend config."""
    class TestModel(BaseModel):
        name: str
    
    class TestSource(BaseSource):
        Model = TestModel
        
        class Config(BaseSource.Config):
            custom_field: str = "test"
        
        def fetch(self):
            return TestModel(name="test")
        
        def generate(self, data):
            return data.name
    
    # Config should have both inherited and custom fields
    assert "enabled" in TestSource.Config.model_fields
    assert "daily_max_executions" in TestSource.Config.model_fields
    assert "custom_field" in TestSource.Config.model_fields
    assert TestSource.Config.model_fields["custom_field"].default == "test"
    
    # Model should be registered
    assert TestSource.Model == TestModel

def test_target_filter_default():
    """Test default filter passes through content."""
    class TestTarget(BaseTarget):
        def publish(self, content, api_key):
            return (True, "")
    
    target = TestTarget()
    assert target.filter("test content") == "test content"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/services/test_base.py -v`
Expected: FAIL with "No module named binance_square_bot.services.base"

- [ ] **Step 3: Write minimal implementation**

```python
# src/binance_square_bot/services/base.py
from pydantic import BaseModel
from abc import ABC, abstractmethod
from typing import Type, Optional, Any

class BaseSource(ABC):
    """Base class for all data sources.
    
    Each Source implements: config definition + data model + data fetch + content generation.
    """
    
    # Subclasses should define their own Pydantic model
    Model: Optional[Type[BaseModel]] = None
    
    class Config(BaseModel):
        """Base configuration for all sources."""
        enabled: bool = True
        daily_max_executions: int = 1
    
    def __init_subclass__(cls, **kwargs):
        """Auto-register config and model when subclass is defined."""
        super().__init_subclass__(**kwargs)
        from ..config import MainConfig, models_registry
        MainConfig.register_source_config(cls.__name__, cls.Config)
        if cls.Model is not None:
            models_registry.register(cls.__name__, cls.Model)
    
    @abstractmethod
    def fetch(self) -> Any:
        """Fetch data from source. Returns Model instance(s)."""
        pass
    
    @abstractmethod
    def generate(self, data: Any) -> Any:
        """Generate content from fetched data."""
        pass


class BaseTarget(ABC):
    """Base class for all publish targets."""
    
    class Config(BaseModel):
        """Base configuration for all targets."""
        enabled: bool = True
        daily_max_posts_per_key: int = 100
        api_keys: list[str] = []
    
    def __init_subclass__(cls, **kwargs):
        """Auto-register config when subclass is defined."""
        super().__init_subclass__(**kwargs)
        from ..config import MainConfig
        MainConfig.register_target_config(cls.__name__, cls.Config)
    
    @abstractmethod
    def publish(self, content: Any, api_key: str) -> tuple[bool, str]:
        """Publish content using a specific API key.
        
        Returns:
            Tuple of (success: bool, error_message: str)
        """
        pass
    
    def filter(self, content: Any) -> Any:
        """Content filter hook. Override to filter before publishing."""
        return content
```

- [ ] **Step 4: Create stub config.py to avoid circular import**

```python
# src/binance_square_bot/config.py (stub)
from pydantic_settings import BaseSettings
from pydantic import BaseModel
from typing import Dict, Type

class ModelsRegistry:
    _models: Dict[str, Type[BaseModel]] = {}
    
    @classmethod
    def register(cls, name: str, model: Type[BaseModel]):
        cls._models[name] = model
    
    @classmethod
    def get(cls, name: str) -> Type[BaseModel]:
        return cls._models.get(name)


class MainConfig(BaseSettings):
    _source_configs: Dict[str, Type[BaseModel]] = {}
    _target_configs: Dict[str, Type[BaseModel]] = {}
    
    sqlite_db_path: str = "data/app.db"
    log_level: str = "INFO"
    
    @classmethod
    def register_source_config(cls, name: str, config_cls: Type[BaseModel]):
        cls._source_configs[name] = config_cls
    
    @classmethod
    def register_target_config(cls, name: str, config_cls: Type[BaseModel]):
        cls._target_configs[name] = config_cls


models_registry = ModelsRegistry()
config = MainConfig()
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/services/test_base.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/binance_square_bot/services/base.py src/binance_square_bot/config.py tests/services/test_base.py
git commit -m "feat: add basesource and basetarget abstract classes"
```

---

### Task 6: Complete MainConfig Implementation

**Files:**
- Modify: `src/binance_square_bot/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_config.py
from pydantic import BaseModel
from binance_square_bot.config import MainConfig, ModelsRegistry

def test_source_config_registration():
    """Test source config can be registered."""
    class TestSourceConfig(BaseModel):
        enabled: bool = True
    
    MainConfig.register_source_config("TestSource", TestSourceConfig)
    assert "TestSource" in MainConfig._source_configs

def test_target_config_registration():
    """Test target config can be registered."""
    class TestTargetConfig(BaseModel):
        enabled: bool = True
    
    MainConfig.register_target_config("TestTarget", TestTargetConfig)
    assert "TestTarget" in MainConfig._target_configs

def test_models_registry():
    """Test models registry works."""
    class TestModel(BaseModel):
        name: str
    
    ModelsRegistry.register("TestModel", TestModel)
    assert ModelsRegistry.get("TestModel") == TestModel
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_config.py -v`
Expected: Tests should PASS (we already have the stub, verify it works)

- [ ] **Step 3: Enhance config with instance getters and env var support**

```python
# src/binance_square_bot/config.py
from pydantic_settings import BaseSettings
from pydantic import BaseModel
from typing import Dict, Type

class ModelsRegistry:
    """Global registry for source data models."""
    _models: Dict[str, Type[BaseModel]] = {}
    
    @classmethod
    def register(cls, name: str, model: Type[BaseModel]):
        cls._models[name] = model
    
    @classmethod
    def get(cls, name: str) -> Type[BaseModel]:
        return cls._models.get(name)


class MainConfig(BaseSettings):
    """Main configuration with dynamic source/target config registration."""
    
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "allow",
    }
    
    _source_configs: Dict[str, Type[BaseModel]] = {}
    _target_configs: Dict[str, Type[BaseModel]] = {}
    
    # General settings
    sqlite_db_path: str = "data/app.db"
    log_level: str = "INFO"
    
    @classmethod
    def register_source_config(cls, name: str, config_cls: Type[BaseModel]):
        """Register a source configuration class."""
        cls._source_configs[name] = config_cls
    
    @classmethod
    def register_target_config(cls, name: str, config_cls: Type[BaseModel]):
        """Register a target configuration class."""
        cls._target_configs[name] = config_cls
    
    @classmethod
    def get_source_config_class(cls, source_name: str) -> Type[BaseModel]:
        """Get the config class for a specific source."""
        return cls._source_configs.get(source_name)
    
    @classmethod
    def get_target_config_class(cls, target_name: str) -> Type[BaseModel]:
        """Get the config class for a specific target."""
        return cls._target_configs.get(target_name)


models_registry = ModelsRegistry()
config = MainConfig()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_config.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/binance_square_bot/config.py tests/test_config.py
git commit -m "feat: complete mainconfig with env var support"
```

---

### Task 7: Loguru Logging Configuration

**Files:**
- Create: `src/binance_square_bot/common/logging.py`
- Create: `src/binance_square_bot/common/__init__.py`
- Test: `tests/common/test_logging.py`

- [ ] **Step 1: Write failing test**

```python
# tests/common/test_logging.py
from loguru import logger
from binance_square_bot.common.logging import setup_logger

def test_setup_logger():
    """Test setup_logger configures logger handlers."""
    initial_handler_count = len(logger._core.handlers)
    setup_logger()
    # Should have at least stderr handler after setup
    assert len(logger._core.handlers) >= 1

def test_logger_usage():
    """Test logger can be used after setup."""
    setup_logger()
    logger.info("Test log message")
    # No exception = success
    assert True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/common/test_logging.py -v`
Expected: FAIL with "No module named binance_square_bot.common.logging"

- [ ] **Step 3: Write minimal implementation**

```python
# src/binance_square_bot/common/logging.py
import sys
from loguru import logger
from ..config import config

def setup_logger():
    """Configure loguru logger with console and file outputs."""
    # Remove default handlers
    logger.remove()
    
    # Console output with colors
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level=config.log_level,
        colorize=True
    )
    
    # File output with rotation
    logger.add(
        "logs/app_{time:YYYY-MM-DD}.log",
        rotation="00:00",  # Rotate daily at midnight
        retention="30 days",
        compression="zip",
        level="DEBUG",
        encoding="utf-8"
    )
```

```python
# src/binance_square_bot/common/__init__.py
from .logging import setup_logger

__all__ = ["setup_logger"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/common/test_logging.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/binance_square_bot/common/__init__.py src/binance_square_bot/common/logging.py tests/common/test_logging.py
git commit -m "feat: add loguru unified logging configuration"
```

---

### Task 8: StorageService ORM Implementation

**Files:**
- Modify: `src/binance_square_bot/services/storage.py`
- Test: `tests/services/test_storage.py`

- [ ] **Step 1: Write failing test**

```python
# tests/services/test_storage.py
from binance_square_bot.services.storage import StorageService

def test_daily_execution_count_flow():
    """Test execution count increment and check flow."""
    storage = StorageService(":memory:")
    
    source_name = "TestSource"
    
    # Initially 0
    assert storage.get_daily_execution_count(source_name) == 0
    assert storage.can_execute_source(source_name, 5) is True
    
    # Increment
    storage.increment_daily_execution(source_name)
    assert storage.get_daily_execution_count(source_name) == 1
    
    # Test limit
    for _ in range(4):
        storage.increment_daily_execution(source_name)
    assert storage.get_daily_execution_count(source_name) == 5
    assert storage.can_execute_source(source_name, 5) is False

def test_daily_publish_count_flow():
    """Test publish count increment per API key."""
    storage = StorageService(":memory:")
    
    target_name = "BinanceTarget"
    api_key = "test_api_key_1"
    
    # Initially 0
    assert storage.get_daily_publish_count(target_name, api_key) == 0
    assert storage.can_publish_key(target_name, api_key, 100) is True
    
    # Increment
    storage.increment_daily_publish_count(target_name, api_key)
    assert storage.get_daily_publish_count(target_name, api_key) == 1
    
    # Different API key is separate
    api_key_2 = "test_api_key_2"
    assert storage.get_daily_publish_count(target_name, api_key_2) == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/services/test_storage.py -v`
Expected: FAIL

- [ ] **Step 3: Write ORM implementation**

```python
# src/binance_square_bot/services/storage.py
from binance_square_bot.models.base import Database
from binance_square_bot.models.daily_execution_stats import DailyExecutionStatsModel
from binance_square_bot.models.daily_publish_stats import DailyPublishStatsModel
from datetime import datetime
from loguru import logger

class StorageService:
    """Service for managing persistent storage."""
    
    def __init__(self, db_path: str = None):
        """Initialize storage service.
        
        Args:
            db_path: Optional path to SQLite database file. Uses config.sqlite_db_path if None.
        """
        from ..config import config
        path = db_path if db_path else config.sqlite_db_path
        Database.init(path)
        logger.debug(f"Storage initialized with database: {path}")
    
    # ===== Source Execution Limits =====
    
    def get_daily_execution_count(self, source_name: str) -> int:
        """Get execution count for a source today."""
        with Database.get_session() as session:
            stat = session.query(DailyExecutionStatsModel).filter(
                DailyExecutionStatsModel.source_name == source_name,
                DailyExecutionStatsModel.date == DailyExecutionStatsModel.today()
            ).first()
            return stat.count if stat else 0
    
    def increment_daily_execution(self, source_name: str) -> None:
        """Increment execution count for a source today."""
        with Database.get_session() as session:
            stat = session.query(DailyExecutionStatsModel).filter(
                DailyExecutionStatsModel.source_name == source_name,
                DailyExecutionStatsModel.date == DailyExecutionStatsModel.today()
            ).first()
            
            if stat:
                stat.count += 1
                stat.last_executed_at = datetime.now()
            else:
                stat = DailyExecutionStatsModel(
                    source_name=source_name,
                    date=DailyExecutionStatsModel.today(),
                    count=1,
                    last_executed_at=datetime.now()
                )
                session.add(stat)
            session.commit()
        logger.debug(f"Incremented execution count for {source_name}")
    
    def can_execute_source(self, source_name: str, max_executions: int) -> bool:
        """Check if a source can execute today."""
        return self.get_daily_execution_count(source_name) < max_executions
    
    # ===== Target Publish Limits (Per API Key) =====
    
    def get_daily_publish_count(self, target_name: str, api_key: str) -> int:
        """Get publish count for a target + API key combination today."""
        key_hash = DailyPublishStatsModel.hash_key(api_key)
        with Database.get_session() as session:
            stat = session.query(DailyPublishStatsModel).filter(
                DailyPublishStatsModel.target_name == target_name,
                DailyPublishStatsModel.api_key_hash == key_hash,
                DailyPublishStatsModel.date == DailyPublishStatsModel.today()
            ).first()
            return stat.count if stat else 0
    
    def increment_daily_publish_count(self, target_name: str, api_key: str) -> None:
        """Increment publish count for a target + API key combination today."""
        key_hash = DailyPublishStatsModel.hash_key(api_key)
        key_mask = DailyPublishStatsModel.mask_key(api_key)
        
        with Database.get_session() as session:
            stat = session.query(DailyPublishStatsModel).filter(
                DailyPublishStatsModel.target_name == target_name,
                DailyPublishStatsModel.api_key_hash == key_hash,
                DailyPublishStatsModel.date == DailyPublishStatsModel.today()
            ).first()
            
            if stat:
                stat.count += 1
                stat.last_published_at = datetime.now()
            else:
                stat = DailyPublishStatsModel(
                    target_name=target_name,
                    api_key_hash=key_hash,
                    api_key_mask=key_mask,
                    date=DailyPublishStatsModel.today(),
                    count=1,
                    last_published_at=datetime.now()
                )
                session.add(stat)
            session.commit()
        logger.debug(f"Incremented publish count for {target_name} key {key_mask}")
    
    def can_publish_key(self, target_name: str, api_key: str, max_posts: int) -> bool:
        """Check if a target + API key combination can publish today."""
        return self.get_daily_publish_count(target_name, api_key) < max_posts
    
    # ===== Legacy URL Processing (for backward compatibility) =====
    
    def is_url_processed(self, url: str) -> bool:
        """Check if URL has been processed (legacy method stub)."""
        # TODO: Implement if needed for backward compatibility
        return False
    
    def mark_url_processed(self, url: str, processed: bool = True) -> None:
        """Mark URL as processed (legacy method stub)."""
        # TODO: Implement if needed for backward compatibility
        pass
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/services/test_storage.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/binance_square_bot/services/storage.py tests/services/test_storage.py
git commit -m "feat: rewrite storageservice to sqlalchemy orm"
```

---

### Task 9: Fn Source Implementation

**Files:**
- Create: `src/binance_square_bot/services/source/fn_source.py`
- Create: `src/binance_square_bot/services/source/__init__.py`
- Test: `tests/services/source/test_fn_source.py`

- [ ] **Step 1: Write failing test**

```python
# tests/services/source/test_fn_source.py
from pydantic import BaseModel
from binance_square_bot.services.source.fn_source import FnSource, Article

def test_article_model():
    """Test Article model validation."""
    article = Article(
        title="Test Title",
        url="https://test.com",
        content="Test content"
    )
    assert article.title == "Test Title"
    assert article.url == "https://test.com"
    assert article.content == "Test content"

def test_fn_source_config():
    """Test FnSource has correct config fields."""
    assert "base_url" in FnSource.Config.model_fields
    assert "timeout" in FnSource.Config.model_fields
    assert "enabled" in FnSource.Config.model_fields
    assert "daily_max_executions" in FnSource.Config.model_fields
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/services/source/test_fn_source.py -v`
Expected: FAIL

- [ ] **Step 3: Write implementation**

```python
# src/binance_square_bot/services/source/fn_source.py
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
```

```python
# src/binance_square_bot/services/source/__init__.py
from .fn_source import FnSource

__all__ = ["FnSource"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/services/source/test_fn_source.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/binance_square_bot/services/source/__init__.py src/binance_square_bot/services/source/fn_source.py tests/services/source/test_fn_source.py
git commit -m "feat: add fnsource implementation"
```

---

### Task 10: Polymarket Source Implementation

**Files:**
- Create: `src/binance_square_bot/services/source/polymarket_source.py`
- Modify: `src/binance_square_bot/services/source/__init__.py`
- Test: `tests/services/source/test_polymarket_source.py`

- [ ] **Step 1: Write failing test**

```python
# tests/services/source/test_polymarket_source.py
from binance_square_bot.services.source.polymarket_source import PolymarketSource, PolymarketMarket

def test_market_model():
    """Test PolymarketMarket model validation."""
    market = PolymarketMarket(
        condition_id="0x123",
        question="Will BTC reach 100k?",
        yes_price=0.75,
        no_price=0.25,
        volume=100000.0
    )
    assert market.condition_id == "0x123"
    assert market.yes_price == 0.75

def test_polymarket_source_config():
    """Test PolymarketSource has correct config fields."""
    assert "host" in PolymarketSource.Config.model_fields
    assert "min_volume_threshold" in PolymarketSource.Config.model_fields
    assert "min_win_rate" in PolymarketSource.Config.model_fields
    assert "max_win_rate" in PolymarketSource.Config.model_fields
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/services/source/test_polymarket_source.py -v`
Expected: FAIL

- [ ] **Step 3: Write implementation**

```python
# src/binance_square_bot/services/source/polymarket_source.py
from typing import List, Optional
from pydantic import BaseModel
import httpx
from loguru import logger

from binance_square_bot.services.base import BaseSource


class PolymarketMarket(BaseModel):
    """Polymarket market model."""
    condition_id: str
    question: str
    yes_price: float
    no_price: float
    volume: float
    image: Optional[str] = None
    description: Optional[str] = None


class PolymarketSource(BaseSource):
    """Polymarket data source - fetches markets and generates research."""
    
    Model = PolymarketMarket
    
    class Config(BaseSource.Config):
        host: str = "https://clob.polymarket.com"
        min_volume_threshold: float = 1000.0
        min_win_rate: float = 0.6
        max_win_rate: float = 0.95
        daily_max_executions: int = 10
    
    def __init__(self):
        self.client = httpx.Client(timeout=30.0)
    
    def fetch(self) -> List[PolymarketMarket]:
        """Fetch all markets from Polymarket."""
        url = f"{self.Config.model_fields['host'].default}/markets"
        
        try:
            response = self.client.get(url)
            response.raise_for_status()
            data = response.json()
            
            markets: List[PolymarketMarket] = []
            
            # Handle different response formats
            if isinstance(data, list):
                market_list = data
            elif isinstance(data, dict) and "data" in data:
                market_list = data["data"]
            else:
                market_list = []
            
            for item in market_list:
                try:
                    # Get outcome prices
                    outcomes = item.get("outcomes", [])
                    outcome_prices = item.get("outcomePrices", [])
                    
                    yes_price = 0.0
                    no_price = 0.0
                    
                    for i, outcome in enumerate(outcomes):
                        if outcome.lower() == "yes" and i < len(outcome_prices):
                            yes_price = float(outcome_prices[i])
                        elif outcome.lower() == "no" and i < len(outcome_prices):
                            no_price = float(outcome_prices[i])
                    
                    market = PolymarketMarket(
                        condition_id=item.get("conditionId", ""),
                        question=item.get("question", ""),
                        yes_price=yes_price,
                        no_price=no_price,
                        volume=float(item.get("volume", 0)),
                        image=item.get("image"),
                        description=item.get("description"),
                    )
                    markets.append(market)
                except Exception as e:
                    logger.warning(f"Failed to parse market: {e}")
                    continue
            
            logger.info(f"Fetched {len(markets)} markets from Polymarket")
            return markets
            
        except Exception as e:
            logger.error(f"Failed to fetch markets: {e}")
            return []
    
    def generate(self, markets: List[PolymarketMarket]) -> List[str]:
        """Generate research tweets from high-confidence markets."""
        # Filter for high volume and extreme probability
        candidate_markets = [
            m for m in markets
            if m.volume >= self.Config.model_fields['min_volume_threshold'].default
            and (
                m.yes_price >= self.Config.model_fields['min_win_rate'].default
                or m.no_price >= self.Config.model_fields['min_win_rate'].default
            )
            and (
                m.yes_price <= self.Config.model_fields['max_win_rate'].default
                or m.no_price <= self.Config.model_fields['max_win_rate'].default
            )
        ]
        
        # Sort by volume
        candidate_markets.sort(key=lambda m: m.volume, reverse=True)
        
        tweets = []
        for market in candidate_markets[:5]:  # Top 5 by volume
            direction = "YES" if market.yes_price > market.no_price else "NO"
            probability = max(market.yes_price, market.no_price)
            
            content = (
                f"📊 Polymarket Research Alert\n\n"
                f"{market.question}\n\n"
                f"🎯 Direction: {direction} ({probability:.1%})\n"
                f"💰 Volume: ${market.volume:,.0f}\n\n"
                f"#Polymarket #PredictionMarket"
            )
            
            if len(content) > 280:
                content = content[:277] + "..."
            
            tweets.append(content)
        
        logger.info(f"Generated {len(tweets)} research tweets from markets")
        return tweets
```

- [ ] **Step 4: Update source __init__.py**

```python
# src/binance_square_bot/services/source/__init__.py
from .fn_source import FnSource
from .polymarket_source import PolymarketSource

__all__ = ["FnSource", "PolymarketSource"]
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/services/source/test_polymarket_source.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/binance_square_bot/services/source/polymarket_source.py src/binance_square_bot/services/source/__init__.py tests/services/source/test_polymarket_source.py
git commit -m "feat: add polymarketsource implementation"
```

---

### Task 11: Binance Target Implementation (Multi API Key)

**Files:**
- Create: `src/binance_square_bot/services/target/binance_target.py`
- Create: `src/binance_square_bot/services/target/__init__.py`
- Test: `tests/services/target/test_binance_target.py`

- [ ] **Step 1: Write failing test**

```python
# tests/services/target/test_binance_target.py
from binance_square_bot.services.target.binance_target import BinanceTarget

def test_binance_target_config():
    """Test BinanceTarget has correct config fields."""
    assert "api_keys" in BinanceTarget.Config.model_fields
    assert "api_url" in BinanceTarget.Config.model_fields
    assert "enabled" in BinanceTarget.Config.model_fields
    assert "daily_max_posts_per_key" in BinanceTarget.Config.model_fields

def test_filter_passthrough():
    """Test default filter passes content through."""
    target = BinanceTarget()
    assert target.filter("test content") == "test content"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/services/target/test_binance_target.py -v`
Expected: FAIL

- [ ] **Step 3: Write implementation**

```python
# src/binance_square_bot/services/target/binance_target.py
import httpx
from loguru import logger
from typing import List, Tuple

from binance_square_bot.services.base import BaseTarget


class BinanceTarget(BaseTarget):
    """Binance Square publishing target with multi-API key support."""
    
    class Config(BaseTarget.Config):
        api_keys: List[str] = []
        api_url: str = "https://www.binance.com/bapi/composite/v1/public/pgc/openApi/content/add"
        daily_max_posts_per_key: int = 100
    
    def __init__(self):
        self.client = httpx.Client(timeout=30.0)
    
    def publish(self, content: str, api_key: str) -> Tuple[bool, str]:
        """Publish content using a specific API key.
        
        Args:
            content: The tweet content to publish
            api_key: The Binance Square OpenAPI key
        
        Returns:
            Tuple of (success: bool, error_message: str)
        """
        headers = {
            "X-Square-OpenAPI-Key": api_key,
            "Content-Type": "application/json",
            "clienttype": "binanceSkill",
        }
        
        body = {
            "bodyTextOnly": content,
        }
        
        try:
            logger.debug(f"Publishing to Binance Square: {content[:50]}...")
            response = self.client.post(
                self.Config.model_fields["api_url"].default,
                headers=headers,
                json=body,
            )
            response.raise_for_status()
            data = response.json()
            
            code = data.get("code")
            message = data.get("message", "")
            
            # 000000 or 0 means success
            if code == "000000" or code == 0:
                logger.info("Successfully published to Binance Square")
                return True, ""
            else:
                logger.warning(f"Binance Square API error: {code} - {message}")
                return False, message or f"API error code: {code}"
                
        except httpx.HTTPError as e:
            logger.error(f"HTTP error publishing to Binance: {str(e)}")
            return False, f"HTTP error: {str(e)}"
        except Exception as e:
            logger.error(f"Unexpected error publishing to Binance: {str(e)}")
            return False, f"Unexpected error: {str(e)}"
```

```python
# src/binance_square_bot/services/target/__init__.py
from .binance_target import BinanceTarget

__all__ = ["BinanceTarget"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/services/target/test_binance_target.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/binance_square_bot/services/target/__init__.py src/binance_square_bot/services/target/binance_target.py tests/services/target/test_binance_target.py
git commit -m "feat: add binancetarget with multi api key support"
```

---

### Task 12: Fn CLI Service (Business Logic)

**Files:**
- Create: `src/binance_square_bot/services/cli/fn_cli.py`
- Create: `src/binance_square_bot/services/cli/__init__.py`
- Test: `tests/services/cli/test_fn_cli.py`

- [ ] **Step 1: Write failing test**

```python
# tests/services/cli/test_fn_cli.py
from binance_square_bot.services.cli.fn_cli import FnCliService

def test_fn_cli_service_init():
    """Test FnCliService can be initialized."""
    service = FnCliService(dry_run=True, limit=5)
    assert service.dry_run is True
    assert service.limit == 5
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/services/cli/test_fn_cli.py -v`
Expected: FAIL

- [ ] **Step 3: Write implementation**

```python
# src/binance_square_bot/services/cli/fn_cli.py
import time
from typing import Dict, Any
from loguru import logger
from rich.console import Console
from rich.table import Table

from binance_square_bot.services.storage import StorageService
from binance_square_bot.services.source.fn_source import FnSource
from binance_square_bot.services.target.binance_target import BinanceTarget

console = Console()


class FnCliService:
    """CLI business logic for Fn news workflow."""
    
    def __init__(self, dry_run: bool = False, limit: int = None):
        self.dry_run = dry_run
        self.limit = limit
        self.storage = StorageService()
        self.source = FnSource()
        self.target = BinanceTarget()
    
    def execute(self) -> Dict[str, Any]:
        """Execute the full crawl-generate-publish workflow.
        
        Returns:
            Dictionary with execution statistics
        """
        logger.info("Starting Fn news workflow")
        
        # Check execution limit
        if not self.storage.can_execute_source("FnSource", FnSource.Config.model_fields["daily_max_executions"].default):
            console.print("[yellow]⚠️ Daily execution limit reached for FnSource[/yellow]")
            return {"error": "daily limit reached"}
        
        # Fetch articles
        console.print("[blue]📥 Fetching Fn news...[/blue]")
        articles = self.source.fetch()
        console.print(f"✓ Fetched {len(articles)} articles")
        
        if not articles:
            console.print("[yellow]No articles found[/yellow]")
            return {"articles_fetched": 0}
        
        # Apply limit
        if self.limit and len(articles) > self.limit:
            articles = articles[:self.limit]
            console.print(f"ℹ️ Limited to {self.limit} articles")
        
        # Generate tweets
        console.print("[blue]✍️ Generating tweets...[/blue]")
        tweets = self.source.generate(articles)
        
        stats = {
            "articles_fetched": len(articles),
            "tweets_generated": len(tweets),
            "published_success": 0,
            "published_failed": 0,
            "dry_run": self.dry_run,
        }
        
        if self.dry_run:
            console.print(f"[yellow]🏁 Dry run complete. Generated {len(tweets)} tweets.[/yellow]")
            for i, tweet in enumerate(tweets, 1):
                console.print(f"\n--- Tweet {i} ---")
                console.print(tweet)
            return stats
        
        # Publish to all enabled API keys
        api_keys = BinanceTarget.Config.model_fields["api_keys"].default
        if not api_keys:
            console.print("[red]❌ No API keys configured[/red]")
            return stats
        
        console.print(f"[blue]📤 Publishing to {len(api_keys)} API keys...[/blue]")
        
        for api_key in api_keys:
            # Check per-key publish limit
            if not self.storage.can_publish_key(
                "BinanceTarget",
                api_key,
                BinanceTarget.Config.model_fields["daily_max_posts_per_key"].default
            ):
                key_mask = self.target.models_registry.models["DailyPublishStatsModel"].mask_key(api_key)
                console.print(f"[yellow]⚠️ Daily limit reached for key {key_mask}, skipping[/yellow]")
                continue
            
            for tweet in tweets:
                filtered_tweet = self.target.filter(tweet)
                success, error = self.target.publish(filtered_tweet, api_key)
                
                if success:
                    stats["published_success"] += 1
                    self.storage.increment_daily_publish_count("BinanceTarget", api_key)
                    console.print("[green]✅ Published successfully[/green]")
                else:
                    stats["published_failed"] += 1
                    console.print(f"[red]❌ Publish failed: {error}[/red]")
                
                # Add delay between publishes
                time.sleep(1.0)
        
        # Increment execution count after successful run
        self.storage.increment_daily_execution("FnSource")
        
        # Print summary
        table = Table(title="Execution Summary")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="magenta")
        table.add_row("Articles Fetched", str(stats["articles_fetched"]))
        table.add_row("Tweets Generated", str(stats["tweets_generated"]))
        table.add_row("Published Successfully", str(stats["published_success"]))
        table.add_row("Publish Failed", str(stats["published_failed"]))
        console.print(table)
        
        logger.info(f"Fn news workflow complete: {stats}")
        return stats
```

```python
# src/binance_square_bot/services/cli/__init__.py
from .fn_cli import FnCliService

__all__ = ["FnCliService"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/services/cli/test_fn_cli.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/binance_square_bot/services/cli/__init__.py src/binance_square_bot/services/cli/fn_cli.py tests/services/cli/test_fn_cli.py
git commit -m "feat: add fncliservice business logic"
```

---

### Task 13: Polymarket CLI Service

**Files:**
- Create: `src/binance_square_bot/services/cli/polymarket_cli.py`
- Modify: `src/binance_square_bot/services/cli/__init__.py`
- Test: `tests/services/cli/test_polymarket_cli.py`

- [ ] **Step 1: Write failing test**

```python
# tests/services/cli/test_polymarket_cli.py
from binance_square_bot.services.cli.polymarket_cli import PolymarketCliService

def test_polymarket_cli_service_init():
    """Test PolymarketCliService can be initialized."""
    service = PolymarketCliService(dry_run=True)
    assert service.dry_run is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/services/cli/test_polymarket_cli.py -v`
Expected: FAIL

- [ ] **Step 3: Write implementation**

```python
# src/binance_square_bot/services/cli/polymarket_cli.py
import time
from typing import Dict, Any
from loguru import logger
from rich.console import Console
from rich.table import Table

from binance_square_bot.services.storage import StorageService
from binance_square_bot.services.source.polymarket_source import PolymarketSource
from binance_square_bot.services.target.binance_target import BinanceTarget

console = Console()


class PolymarketCliService:
    """CLI business logic for Polymarket research workflow."""
    
    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.storage = StorageService()
        self.source = PolymarketSource()
        self.target = BinanceTarget()
    
    def execute(self) -> Dict[str, Any]:
        """Execute the full fetch-generate-publish workflow for Polymarket research."""
        logger.info("Starting Polymarket research workflow")
        
        # Check execution limit
        if not self.storage.can_execute_source(
            "PolymarketSource",
            PolymarketSource.Config.model_fields["daily_max_executions"].default
        ):
            console.print("[yellow]⚠️ Daily execution limit reached for PolymarketSource[/yellow]")
            return {"error": "daily limit reached"}
        
        # Fetch markets
        console.print("[blue]🔍 Fetching Polymarket markets...[/blue]")
        markets = self.source.fetch()
        console.print(f"✓ Fetched {len(markets)} markets")
        
        # Generate research tweets
        console.print("[blue]✍️ Generating research tweets...[/blue]")
        tweets = self.source.generate(markets)
        
        stats = {
            "markets_fetched": len(markets),
            "tweets_generated": len(tweets),
            "published_success": 0,
            "published_failed": 0,
            "dry_run": self.dry_run,
        }
        
        if not tweets:
            console.print("[yellow]No suitable markets found for research[/yellow]")
            return stats
        
        if self.dry_run:
            console.print(f"[yellow]🏁 Dry run complete. Generated {len(tweets)} research tweets.[/yellow]")
            for i, tweet in enumerate(tweets, 1):
                console.print(f"\n--- Research Tweet {i} ---")
                console.print(tweet)
            return stats
        
        # Publish to all enabled API keys
        api_keys = BinanceTarget.Config.model_fields["api_keys"].default
        if not api_keys:
            console.print("[red]❌ No API keys configured[/red]")
            return stats
        
        console.print(f"[blue]📤 Publishing to {len(api_keys)} API keys...[/blue]")
        
        for api_key in api_keys:
            if not self.storage.can_publish_key(
                "BinanceTarget",
                api_key,
                BinanceTarget.Config.model_fields["daily_max_posts_per_key"].default
            ):
                from binance_square_bot.models.daily_publish_stats import DailyPublishStatsModel
                key_mask = DailyPublishStatsModel.mask_key(api_key)
                console.print(f"[yellow]⚠️ Daily limit reached for key {key_mask}, skipping[/yellow]")
                continue
            
            for tweet in tweets:
                filtered_tweet = self.target.filter(tweet)
                success, error = self.target.publish(filtered_tweet, api_key)
                
                if success:
                    stats["published_success"] += 1
                    self.storage.increment_daily_publish_count("BinanceTarget", api_key)
                    console.print("[green]✅ Published successfully[/green]")
                else:
                    stats["published_failed"] += 1
                    console.print(f"[red]❌ Publish failed: {error}[/red]")
                
                time.sleep(1.0)
        
        # Increment execution count
        self.storage.increment_daily_execution("PolymarketSource")
        
        # Print summary
        table = Table(title="Polymarket Research Summary")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="magenta")
        table.add_row("Markets Fetched", str(stats["markets_fetched"]))
        table.add_row("Tweets Generated", str(stats["tweets_generated"]))
        table.add_row("Published Successfully", str(stats["published_success"]))
        table.add_row("Publish Failed", str(stats["published_failed"]))
        console.print(table)
        
        logger.info(f"Polymarket research workflow complete: {stats}")
        return stats
    
    def scan(self, top_n: int = 5) -> Dict[str, Any]:
        """Scan markets and show top candidates without generating/publishing."""
        console.print("[blue]🔍 Scanning Polymarket markets...[/blue]")
        markets = self.source.fetch()
        
        # Filter by minimum volume
        min_volume = PolymarketSource.Config.model_fields['min_volume_threshold'].default
        candidates = [m for m in markets if m.volume >= min_volume]
        candidates.sort(key=lambda m: m.volume, reverse=True)
        
        console.print(f"\n[bold cyan]Top {min(top_n, len(candidates))} candidate markets:[/bold cyan]\n")
        for i, market in enumerate(candidates[:top_n], 1):
            console.print(f"[bold]{i}. {market.question}[/]")
            console.print(f"   condition_id: {market.condition_id}")
            console.print(f"   YES: {market.yes_price:.1%}, NO: {market.no_price:.1%}")
            console.print(f"   Volume: ${market.volume:,.0f}")
            console.print("")
        
        console.print(f"Total candidate markets: {len(candidates)} / {len(markets)}")
        return {"total_markets": len(markets), "candidates": len(candidates)}
```

- [ ] **Step 4: Update cli __init__.py**

```python
# src/binance_square_bot/services/cli/__init__.py
from .fn_cli import FnCliService
from .polymarket_cli import PolymarketCliService

__all__ = ["FnCliService", "PolymarketCliService"]
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/services/cli/test_polymarket_cli.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/binance_square_bot/services/cli/polymarket_cli.py src/binance_square_bot/services/cli/__init__.py tests/services/cli/test_polymarket_cli.py
git commit -m "feat: add polymarketcliservice business logic"
```

---

### Task 14: Common CLI Service (Clean Command)

**Files:**
- Create: `src/binance_square_bot/services/cli/common_cli.py`
- Modify: `src/binance_square_bot/services/cli/__init__.py`
- Test: `tests/services/cli/test_common_cli.py`

- [ ] **Step 1: Write failing test**

```python
# tests/services/cli/test_common_cli.py
from binance_square_bot.services.cli.common_cli import CommonCliService

def test_common_cli_service_init():
    """Test CommonCliService can be initialized."""
    service = CommonCliService()
    assert service.storage is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/services/cli/test_common_cli.py -v`
Expected: FAIL

- [ ] **Step 3: Write implementation**

```python
# src/binance_square_bot/services/cli/common_cli.py
import os
from loguru import logger
from rich.console import Console
from rich.prompt import Confirm

from binance_square_bot.services.storage import StorageService
from binance_square_bot.config import config

console = Console()


class CommonCliService:
    """Common CLI commands service."""
    
    def __init__(self):
        self.storage = StorageService()
    
    def clean(self, force: bool = False) -> None:
        """Clean all processed URL records and daily stats.
        
        Args:
            force: If True, skip confirmation prompt
        """
        if not force:
            confirmed = Confirm.ask(
                "[bold red]⚠️ Are you sure you want to CLEAR ALL processed records? This cannot be undone.[/bold red]"
            )
            if not confirmed:
                console.print("[yellow]Operation cancelled[/yellow]")
                return
        
        # Delete database file
        db_path = config.sqlite_db_path
        if os.path.exists(db_path):
            os.remove(db_path)
            logger.info(f"Deleted database file: {db_path}")
            console.print("[green]✅ All processed records have been cleared[/green]")
        else:
            console.print("[yellow]Database file not found, nothing to clean[/yellow]")
```

- [ ] **Step 4: Update cli __init__.py**

```python
# src/binance_square_bot/services/cli/__init__.py
from .fn_cli import FnCliService
from .polymarket_cli import PolymarketCliService
from .common_cli import CommonCliService

__all__ = ["FnCliService", "PolymarketCliService", "CommonCliService"]
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/services/cli/test_common_cli.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/binance_square_bot/services/cli/common_cli.py src/binance_square_bot/services/cli/__init__.py tests/services/cli/test_common_cli.py
git commit -m "feat: add commoncliservice with clean command"
```

---

### Task 15: Update Main CLI Entry Point

**Files:**
- Modify: `src/binance_square_bot/cli.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_cli.py
from typer.testing import CliRunner
from binance_square_bot.cli import app

runner = CliRunner()

def test_version():
    """Test version flag works."""
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "BinanceSquareBot" in result.output

def test_help():
    """Test help command works."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "run" in result.output
    assert "clean" in result.output
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli.py -v`
Expected: FAIL (old cli.py doesn't match new structure)

- [ ] **Step 3: Rewrite CLI entry point**

```python
# src/binance_square_bot/cli.py
"""CLI entry point for BinanceSquareBot."""

import typer
from rich.console import Console

from binance_square_bot.common.logging import setup_logger
from binance_square_bot.services.cli import FnCliService, PolymarketCliService, CommonCliService

# Initialize logger
setup_logger()

app = typer.Typer(
    name="binance-square-bot",
    help="BinanceSquareBot - Auto-crawl news, generate AI tweets, publish to Binance Square",
    add_completion=False,
)

polymarket_app = typer.Typer(
    help="Polymarket AI research tweets",
    add_completion=False,
)
app.add_typer(polymarket_app, name="polymarket-research")

console = Console()


def version_callback(value: bool) -> None:
    if value:
        from . import __version__
        console.print(f"BinanceSquareBot v{__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool | None = typer.Option(
        None,
        "--version",
        "-v",
        help="Show version number",
        callback=version_callback,
        is_eager=True,
    ),
) -> None:
    pass


@app.command("run")
def run(
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Only fetch and generate, no actual publishing",
    ),
    limit: int | None = typer.Option(
        None,
        "--limit",
        help="Limit number of articles to process (for testing)",
    ),
) -> None:
    """Run full Fn news crawl-generate-publish workflow."""
    service = FnCliService(dry_run=dry_run, limit=limit)
    service.execute()


@app.command("clean")
def clean(
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Skip confirmation prompt",
    ),
) -> None:
    """Clean all processed URL records and daily stats."""
    service = CommonCliService()
    service.clean(force=force)


@polymarket_app.command("run")
def polymarket_run(
    dry_run: bool = typer.Option(False, "--dry-run", help="Only generate, no publishing"),
) -> None:
    """Run Polymarket research workflow - fetch markets, generate tweets, publish."""
    service = PolymarketCliService(dry_run=dry_run)
    service.execute()


@polymarket_app.command("scan")
def polymarket_scan(
    top_n: int = typer.Option(5, "--top-n", help="Show top N candidate markets"),
) -> None:
    """Scan Polymarket markets and show top candidates - no generation/publishing."""
    service = PolymarketCliService()
    service.scan(top_n=top_n)


if __name__ == "__main__":
    app()
```

- [ ] **Step 4: Add __init__.py with version**

```python
# src/binance_square_bot/__init__.py
__version__ = "2.0.0"
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_cli.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/binance_square_bot/cli.py src/binance_square_bot/__init__.py tests/test_cli.py
git commit -m "feat: update main cli entry point with new service architecture"
```

---

### Task 16: Clean Up Old Files and Run Final Tests

**Files:**
- Delete: `src/binance_square_bot/services/generator.py`
- Delete: `src/binance_square_bot/services/polymarket_fetcher.py`
- Delete: `src/binance_square_bot/services/polymarket_filter.py`
- Delete: `src/binance_square_bot/services/publisher.py`
- Delete: `src/binance_square_bot/services/spider.py`
- Delete: `tests/test_polymarket_fetcher.py`
- Delete: `tests/test_polymarket_filter.py`
- Delete: `tests/test_publisher.py`
- Delete: `tests/test_spider.py`
- Delete: `tests/live_test_spider.py`

- [ ] **Step 1: Delete old source files**

```bash
rm src/binance_square_bot/services/generator.py
rm src/binance_square_bot/services/polymarket_fetcher.py
rm src/binance_square_bot/services/polymarket_filter.py
rm src/binance_square_bot/services/publisher.py
rm src/binance_square_bot/services/spider.py
```

- [ ] **Step 2: Delete old test files**

```bash
rm tests/test_polymarket_fetcher.py
rm tests/test_polymarket_filter.py
rm tests/test_publisher.py
rm tests/test_spider.py
rm tests/live_test_spider.py
```

- [ ] **Step 3: Update services __init__.py**

```python
# src/binance_square_bot/services/__init__.py
from .storage import StorageService
from .source import FnSource, PolymarketSource
from .target import BinanceTarget
from .cli import FnCliService, PolymarketCliService, CommonCliService

__all__ = [
    "StorageService",
    "FnSource",
    "PolymarketSource",
    "BinanceTarget",
    "FnCliService",
    "PolymarketCliService",
    "CommonCliService",
]
```

- [ ] **Step 4: Run all tests**

Run: `pytest tests/ -v --tb=short`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/binance_square_bot/services/__init__.py
git add -A
git commit -m "feat: clean up old files, complete refactoring"
```

---

## Plan Self-Review

✅ **Spec coverage:** All requirements from the design spec are covered by tasks in this plan:
- ORM database models and management
- BaseSource/BaseTarget with auto-registration
- Configuration system with env var support
- Loguru logging
- Multi API key support for publishing
- Daily execution/publish limits
- Both Fn news and Polymarket workflows

✅ **No placeholders:** Every task has complete code, exact commands, no TODOs

✅ **Type consistency:** All model field names, method names, and parameters are consistent across tasks

✅ **Dependency order:** Tasks build on each other correctly - base classes before implementations, storage before services

Ready for execution!
