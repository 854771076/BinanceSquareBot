# BinanceSquareBot 代码重构设计文档

**日期**: 2026-04-21  
**版本**: v1.1

## 1. 重构目标

将现有代码重构为更具扩展性的插件式架构：
- Source 和 Target 分别有基类，实现类继承
- 所有逻辑在一个类中统一管理
- 通过配置动态启用/禁用实现类
- 配置统一动态加载
- 日志统一使用 loguru
- CLI 业务逻辑独立封装

## 2. 目录结构

```
binance_square_bot/
├── config.py                    # 主配置入口，动态加载所有 source/target 配置
├── cli.py                       # CLI 入口，只保留命令定义和转发
├── models/                      # 全局通用数据模型（SQLAlchemy ORM）
│   ├── __init__.py
│   ├── base.py                  # ORM 基类和数据库连接管理
│   ├── daily_execution_stats.py # Source 每日执行次数统计
│   └── daily_publish_stats.py   # Target 每日发布统计（按 target + api_key 维度）
├── common/                      # 通用模块
│   ├── __init__.py
│   └── logging.py               # loguru 统一配置
└── services/
    ├── __init__.py
    ├── base.py                  # BaseSource, BaseTarget 基类定义
    ├── storage.py               # 数据存储服务
    ├── source/                  # 数据源实现：每个 source 自包含完整业务闭环
    │   ├── __init__.py          # 导入所有 source，触发自动注册
    │   ├── fn_source.py         # Fn 新闻爬虫 + 推文生成
    │   └── polymarket_source.py # Polymarket 数据获取 + 研报生成
    ├── target/                  # 发布目标实现
    │   ├── __init__.py          # 导入所有 target，触发自动注册
    │   └── binance_target.py    # 币安广场发布
    └── cli/                     # CLI 业务逻辑封装
        ├── __init__.py
        ├── fn_cli.py            # run 命令业务逻辑
        ├── polymarket_cli.py    # Polymarket 研报命令业务逻辑
        └── common_cli.py        # 通用命令（如 clean）
```

## 3. 核心架构设计

### 3.1 BaseSource 基类

```python
# services/base.py
from pydantic import BaseModel
from abc import ABC, abstractmethod
from typing import Type, Optional, Any

class BaseSource(ABC):
    """所有数据源的基类
    
    每个 Source 实现完整闭环：配置定义 + 数据模型 + 数据采集 + 内容生成
    """
    
    # 子类必须定义自己的数据模型（可选）
    Model: Optional[Type[BaseModel]] = None
    
    class Config(BaseModel):
        """每个 Source 子类必须定义自己的配置类"""
        enabled: bool = True
        daily_max_executions: int = 1  # 每日最大执行次数
    
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        # 自动注册配置和模型
        from ..config import MainConfig, models_registry
        MainConfig.register_source_config(cls.__name__, cls.Config)
        if cls.Model is not None:
            models_registry.register(cls.__name__, cls.Model)
    
    @abstractmethod
    def fetch(self) -> Any:
        """采集数据，返回 Model 类型的实例或列表"""
        pass
    
    @abstractmethod
    def generate(self, data: Any) -> Any:
        """生成内容，入参是 fetch 返回的 Model 数据"""
        pass
```

### 3.2 BaseTarget 基类

```python
class BaseTarget(ABC):
    """所有发布目标的基类"""
    
    class Config(BaseModel):
        enabled: bool = True
        daily_max_posts_per_key: int = 100  # 每个 API key 的每日发布上限
        api_keys: list[str] = []            # API key 列表
    
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        from ..config import MainConfig
        MainConfig.register_target_config(cls.__name__, cls.Config)
    
    @abstractmethod
    def publish(self, content: Any, api_key: str) -> tuple[bool, str]:
        """使用单个 API key 发布内容
        
        Returns:
            (success: bool, error_message: str)
        """
        pass
    
    def filter(self, content: Any) -> Any:
        """统一内容过滤（停用词、敏感词等），可被子类重写"""
        return content
```

### 3.3 配置系统

```python
# config.py
from pydantic_settings import BaseSettings
from pydantic import BaseModel
from typing import Dict, Type

class ModelsRegistry:
    """全局数据模型注册表"""
    _models: Dict[str, Type[BaseModel]] = {}
    
    @classmethod
    def register(cls, name: str, model: Type[BaseModel]):
        cls._models[name] = model
    
    @classmethod
    def get(cls, name: str) -> Type[BaseModel]:
        return cls._models.get(name)


class MainConfig(BaseSettings):
    """主配置，动态加载所有 source/target 的配置定义"""
    
    _source_configs: Dict[str, Type[BaseModel]] = {}
    _target_configs: Dict[str, Type[BaseModel]] = {}
    
    # 通用配置
    sqlite_db_path: str = "data/processed_urls.db"
    log_level: str = "INFO"
    
    @classmethod
    def register_source_config(cls, name: str, config_cls: Type[BaseModel]):
        cls._source_configs[name] = config_cls
    
    @classmethod
    def register_target_config(cls, name: str, config_cls: Type[BaseModel]):
        cls._target_configs[name] = config_cls
    
    def get_source_config(self, source_name: str) -> BaseModel:
        """获取指定 source 的配置实例"""
        return self.source_configs.get(source_name)
    
    def get_target_config(self, target_name: str) -> BaseModel:
        """获取指定 target 的配置实例"""
        return self.target_configs.get(target_name)


# 全局实例
models_registry = ModelsRegistry()
config = MainConfig()
```

### 3.4 日志系统

```python
# common/logging.py
import sys
from loguru import logger

def setup_logger():
    """统一配置 loguru"""
    # 移除默认的 stderr 输出
    logger.remove()
    
    # 添加控制台输出
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level=config.log_level,
        colorize=True
    )
    
    # 添加文件输出
    logger.add(
        "logs/app_{time:YYYY-MM-DD}.log",
        rotation="00:00",  # 每天轮转
        retention="30 days",
        compression="zip",
        level="DEBUG"
    )
```

## 4. Source 实现示例

### 4.1 FnSource（Fn 新闻）

```python
# services/source/fn_source.py
from pydantic import BaseModel
from datetime import datetime
from ..base import BaseSource

class Article(BaseModel):
    """Fn 新闻文章模型"""
    title: str
    url: str
    content: str
    published_at: datetime | None = None


class FnSource(BaseSource):
    """Fn 新闻数据源"""
    
    Model = Article
    
    class Config(BaseSource.Config):
        base_url: str = "https://api.foresightnews.pro"
        timeout: int = 30
    
    def fetch(self) -> list[Article]:
        """爬取 Fn 新闻列表"""
        # ... 爬虫实现
    
    def generate(self, articles: list[Article]) -> list[str]:
        """将文章生成推文内容"""
        # ... 生成实现
```

### 4.2 PolymarketSource（预测市场）

```python
# services/source/polymarket_source.py
from pydantic import BaseModel
from ..base import BaseSource

class PolymarketMarket(BaseModel):
    """Polymarket 市场模型"""
    condition_id: str
    question: str
    yes_price: float
    no_price: float
    volume: float


class PolymarketSource(BaseSource):
    """Polymarket 数据源"""
    
    Model = PolymarketMarket
    
    class Config(BaseSource.Config):
        host: str = "https://clob.polymarket.com"
        min_volume_threshold: float = 1000.0
        min_win_rate: float = 0.6
        max_win_rate: float = 0.9
    
    def fetch(self) -> list[PolymarketMarket]:
        """获取 Polymarket 市场数据"""
        # ... 实现
    
    def generate(self, markets: list[PolymarketMarket]) -> list[str]:
        """生成投资研报内容"""
        # ... 实现
```

## 5. Target 实现示例

### 5.1 BinanceTarget（币安广场）

```python
# services/target/binance_target.py
from ..base import BaseTarget
import httpx

class BinanceTarget(BaseTarget):
    """币安广场发布目标"""
    
    class Config(BaseTarget.Config):
        api_keys: list[str] = []
        api_url: str = "https://www.binance.com/bapi/composite/v1/public/pgc/openApi/content/add"
    
    def __init__(self):
        self.client = httpx.Client(timeout=30.0)
    
    def publish(self, content: str, api_key: str) -> tuple[bool, str]:
        """使用指定 API key 发布到币安广场"""
        headers = {
            "X-Square-OpenAPI-Key": api_key,
            "Content-Type": "application/json",
            "clienttype": "binanceSkill",
        }
        body = {"bodyTextOnly": content}
        
        try:
            response = self.client.post(
                self.Config.api_url,
                headers=headers,
                json=body,
            )
            response.raise_for_status()
            data = response.json()
            
            code = data.get("code")
            if code == "000000" or code == 0:
                return True, ""
            return False, data.get("message", "")
            
        except Exception as e:
            return False, str(e)
```

## 6. CLI 业务流程

### 6.1 发布流程

```
CLI 命令调用 → CliService.execute()
  │
  ├─ 初始化所有 enabled 的 Source
  │   └─ source.fetch() → 采集数据
  │   └─ source.generate() → 生成内容
  │
  ├─ 遍历所有 enabled 的 Target
  │   └─ 遍历该 Target 的所有 API keys
  │       ├─ 检查 daily_publish_stats 今日发布数 < daily_max_posts
  │       ├─ target.filter(content) → 内容过滤
  │       ├─ target.publish(content, api_key) → 发布
  │       └─ 更新 daily_publish_stats 计数
  │
  └─ 返回执行结果
```

### 6.2 CLI Service 示例

```python
# services/cli/fn_cli.py
from binance_square_bot.services.storage import Storage
from binance_square_bot.services.source.fn_source import FnSource
from binance_square_bot.services.target.binance_target import BinanceTarget

class FnCliService:
    """Fn 新闻流程 CLI 业务逻辑"""
    
    def __init__(self, dry_run: bool = False, limit: int = None):
        self.dry_run = dry_run
        self.limit = limit
        self.storage = Storage()
        self.source = FnSource()
        self.target = BinanceTarget()
    
    def execute(self):
        """执行完整的爬取-生成-发布流程"""
        # ... 业务逻辑实现
```

## 7. 自动注册机制

### 7.1 Source 自动注册

```python
# services/source/__init__.py
# 导入所有 source 类，触发 __init_subclass__ 自动注册配置和模型
from .fn_source import FnSource
from .polymarket_source import PolymarketSource

__all__ = ["FnSource", "PolymarketSource"]
```

### 7.2 Target 自动注册

```python
# services/target/__init__.py
from .binance_target import BinanceTarget

__all__ = ["BinanceTarget"]
```

## 8. ORM 数据库设计（SQLAlchemy）

### 8.1 ORM 基类和数据库管理

```python
# models/base.py
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

### 8.2 Source 每日执行统计表

```python
# models/daily_execution_stats.py
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

### 8.3 Target 每日发布统计表（按 API key 维度）

```python
# models/daily_publish_stats.py
from sqlalchemy import Column, String, Integer, DateTime
from datetime import datetime
import hashlib
from .base import Base

class DailyPublishStatsModel(Base):
    __tablename__ = "daily_publish_stats"
    
    target_name = Column(String, primary_key=True, index=True)
    api_key_hash = Column(String, primary_key=True, index=True)  # API key 哈希（避免存明文）
    api_key_mask = Column(String)                                  # 脱敏显示（如 "xxxx...abcd"）
    date = Column(String, primary_key=True, index=True)           # YYYY-MM-DD
    count = Column(Integer, default=0)
    last_published_at = Column(DateTime)
    
    @classmethod
    def today(cls) -> str:
        return datetime.now().strftime("%Y-%m-%d")
    
    @classmethod
    def hash_key(cls, api_key: str) -> str:
        """API key 哈希，用于索引"""
        return hashlib.sha256(api_key.encode()).hexdigest()[:16]
    
    @classmethod
    def mask_key(cls, api_key: str) -> str:
        """API key 脱敏显示"""
        if len(api_key) <= 8:
            return api_key
        return f"{api_key[:4]}...{api_key[-4:]}"
```

### 8.4 Storage Service ORM 实现

```python
# services/storage.py
from models.base import Database
from models.daily_execution_stats import DailyExecutionStatsModel
from models.daily_publish_stats import DailyPublishStatsModel
from datetime import datetime

class StorageService:
    def __init__(self, db_path: str = None):
        if db_path:
            Database.init(db_path)
        else:
            Database.init()
    
    # ===== Source 执行限制 =====
    def get_daily_execution_count(self, source_name: str) -> int:
        """获取 source 今日已执行次数"""
        with Database.get_session() as session:
            stat = session.query(DailyExecutionStatsModel).filter(
                DailyExecutionStatsModel.source_name == source_name,
                DailyExecutionStatsModel.date == DailyExecutionStatsModel.today()
            ).first()
            return stat.count if stat else 0
    
    def increment_daily_execution(self, source_name: str) -> None:
        """递增 source 今日执行次数"""
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
    
    def can_execute_source(self, source_name: str, max_executions: int) -> bool:
        """检查 source 今日是否还能执行"""
        return self.get_daily_execution_count(source_name) < max_executions
    
    # ===== Target 发布限制（按 API key 维度）=====
    def get_daily_publish_count(self, target_name: str, api_key: str) -> int:
        """获取 target + api_key 今日已发布次数"""
        key_hash = DailyPublishStatsModel.hash_key(api_key)
        with Database.get_session() as session:
            stat = session.query(DailyPublishStatsModel).filter(
                DailyPublishStatsModel.target_name == target_name,
                DailyPublishStatsModel.api_key_hash == key_hash,
                DailyPublishStatsModel.date == DailyPublishStatsModel.today()
            ).first()
            return stat.count if stat else 0
    
    def increment_daily_publish_count(self, target_name: str, api_key: str) -> None:
        """递增 target + api_key 今日发布次数"""
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
    
    def can_publish_key(self, target_name: str, api_key: str, max_posts: int) -> bool:
        """检查该 target + api_key 今日是否还能发布"""
        return self.get_daily_publish_count(target_name, api_key) < max_posts
```

### 8.5 多 API Key 发布流程

```
Source 生成内容后：
  ├─ 遍历所有 enabled 的 Target
  │   └─ 遍历该 Target 的每个 api_key：
  │       ├─ 检查该 target + api_key 今日发布数 < daily_max_posts_per_key
  │       ├─ 如超限，跳过该 API key
  │       ├─ 否则执行发布：
  │       │   ├─ target.filter(content) → 内容过滤
  │       │   ├─ success, msg = target.publish(content, api_key)
  │       │   └─ 发布成功则 increment_daily_publish_count(target_name, api_key)
  │       └─ （可选）每个 key 发布后加间隔 delay
  └─ 汇总所有 API key 的发布结果
```

## 9. 关键设计原则

1. **单一职责**：每个 Source 只负责自己的数据源采集和内容生成；每个 Target 只负责发布
2. **开闭原则**：新增 Source/Target 只需新增一个类，无需修改现有代码
3. **依赖倒置**：CLI Service 依赖基类接口，不依赖具体实现
4. **配置驱动**：所有实现的启用/禁用、参数都通过配置控制
5. **自动发现**：通过 `__init_subclass__` 和 `__init__.py` 导入实现自动注册
6. **安全设计**：API key 只存哈希索引，不存明文，避免泄露

## 10. 迁移计划

1. 新增 `models/base.py` ORM 基类和数据库管理
2. 新增 `models/daily_execution_stats.py` 执行统计模型
3. 更新 `models/daily_publish_stats.py` 发布统计模型（按 API key 维度）
4. 迁移 `services/base.py` 基类（含 daily_max_executions 配置）
5. 迁移 `config.py` 配置系统和注册表
6. 迁移 `common/logging.py` 日志配置
7. 迁移 Source 实现（`fn_source.py`、`polymarket_source.py`）
8. 迁移 Target 实现（`binance_target.py`，多 API key 支持）
9. 更新 `services/storage.py` 为 ORM 实现
10. 迁移 CLI Services（`fn_cli.py`、`polymarket_cli.py`、`common_cli.py`）
11. 更新 `cli.py` 入口
12. 删除旧文件
13. 测试验证
