"""
@file config.py
@description 应用配置，使用pydantic-settings从环境变量加载，支持动态源/目标配置注册
@design-doc docs/03-backend-design/domain-model.md
@task-id BE-02
@created-by fullstack-dev-workflow
"""


from pydantic_settings import BaseSettings
from pydantic import BaseModel
from typing import Dict, Type, Optional


class ModelsRegistry:
    """Global registry for source data models."""
    _models: Dict[str, Type[BaseModel]] = {}

    @classmethod
    def register(cls, name: str, model: Type[BaseModel]):
        cls._models[name] = model

    @classmethod
    def get(cls, name: str) -> Optional[Type[BaseModel]]:
        return cls._models.get(name)


class MainConfig(BaseSettings):
    """Main configuration with dynamic source/target config registration."""

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "allow",
    }

    # General settings
    sqlite_db_path: str = "data/app.db"
    log_level: str = "INFO"

    # 币安API密钥列表，逗号分隔
    binance_api_keys: list[str] = []

    # Fn新闻列表URL
    fn_news_url: str = "https://news.fn.org/news"

    # LLM配置
    llm_model: str = "gpt-4o-mini"
    llm_base_url: str = "https://api.openai.com/v1"
    llm_api_key: str = ""

    # 生成配置
    max_retries: int = 3
    min_chars: int = 101
    max_chars: int = 799
    max_hashtags: int = 2
    max_mentions: int = 2

    # 发布限制
    daily_max_posts: int = 100
    publish_interval_seconds: float = 1.0  # 单账号连续两篇推文发布间隔（秒）
    max_concurrent_accounts: int = 3  # 最大并发账号数
    max_concurrent_generations: int = 3  # 最大并发生成数（Polymarket研报生成）

    # Polymarket API 配置
    enable_polymarket: bool = True  # 是否启用 Polymarket 投资研报功能
    polymarket_host: str = "https://clob.polymarket.com"
    polymarket_chain_id: int = 137  # Polygon
    min_volume_threshold: float = 1000.0  # 最小交易量阈值

    @classmethod
    def register_source_config(cls, name: str, config_cls: Type[BaseModel]):
        """Register a source configuration class."""
        cls._source_configs[name] = config_cls

    @classmethod
    def register_target_config(cls, name: str, config_cls: Type[BaseModel]):
        """Register a target configuration class."""
        cls._target_configs[name] = config_cls

    @classmethod
    def get_source_config_class(cls, source_name: str) -> Optional[Type[BaseModel]]:
        """Get the config class for a specific source."""
        return cls._source_configs.get(source_name)

    @classmethod
    def get_target_config_class(cls, target_name: str) -> Optional[Type[BaseModel]]:
        """Get the config class for a specific target."""
        return cls._target_configs.get(target_name)


# Class-level registry (outside the Pydantic model so Pydantic doesn't process them as fields)
MainConfig._source_configs: Dict[str, Type[BaseModel]] = {}
MainConfig._target_configs: Dict[str, Type[BaseModel]] = {}


models_registry = ModelsRegistry()
config = MainConfig()
