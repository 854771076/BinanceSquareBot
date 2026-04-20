"""
@file config.py
@description 应用配置，使用pydantic-settings从环境变量加载，支持动态源/目标配置注册
@design-doc docs/03-backend-design/domain-model.md
@task-id BE-02
@created-by fullstack-dev-workflow
"""


from pydantic_settings import BaseSettings
from pydantic import BaseModel
from typing import Dict, Type, Optional, Any
import os


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
    """Main configuration with dynamic source/target config registration.

    Environment variable naming convention:
    - General: SQLITE_DB_PATH, LOG_LEVEL
    - Source: {SOURCE_NAME}_{FIELD_NAME} (e.g. FN_SOURCE_ENABLED, POLYMARKET_SOURCE_HOST)
    - Target: {TARGET_NAME}_{FIELD_NAME} (e.g. BINANCE_TARGET_API_KEYS)

    Example .env:
        FN_SOURCE_ENABLED=true
        FN_SOURCE_DAILY_MAX_EXECUTIONS=5
        POLYMARKET_SOURCE_HOST=https://clob.polymarket.com
        BINANCE_TARGET_API_KEYS=key1,key2
    """

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "allow",
    }

    # General settings
    sqlite_db_path: str = "data/app.db"
    log_level: str = "INFO"

    # LLM配置
    llm_model: str = "gpt-4o-mini"
    llm_base_url: str = "https://api.openai.com/v1"
    llm_api_key: str = ""

    # 生成配置
    max_retries: int = 3
    min_chars: int = 101
    max_chars: int = 799
    max_hashtags: int = 3
    max_mentions: int = 3

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

    def _get_env_prefix(self, name: str) -> str:
        """Convert class name to environment variable prefix.

        Example: "FnSource" → "FN_SOURCE", "BinanceTarget" → "BINANCE_TARGET"
        """
        for suffix in ["Source", "Target"]:
            if name.endswith(suffix):
                return f"{name[:-len(suffix)]}_{suffix}".upper()
        return name.upper()

    def get_source_config(self, source_name: str) -> Optional[BaseModel]:
        """Get instantiated config for a specific source, loaded from env vars.

        Args:
            source_name: Name of the source class (e.g. "FnSource", "PolymarketSource")

        Returns:
            Config instance with values loaded from environment variables
        """
        config_cls = self._source_configs.get(source_name)
        if not config_cls:
            return None
        return self._load_nested_config(config_cls, prefix=f"{self._get_env_prefix(source_name)}_")

    def get_target_config(self, target_name: str) -> Optional[BaseModel]:
        """Get instantiated config for a specific target, loaded from env vars.

        Args:
            target_name: Name of the target class (e.g. "BinanceTarget")

        Returns:
            Config instance with values loaded from environment variables
        """
        config_cls = self._target_configs.get(target_name)
        if not config_cls:
            return None
        return self._load_nested_config(config_cls, prefix=f"{self._get_env_prefix(target_name)}_")

    def _load_nested_config(self, config_cls: Type[BaseModel], prefix: str) -> BaseModel:
        """Load a nested config class from environment variables.

        Args:
            config_cls: The Pydantic config class to instantiate
            prefix: Environment variable prefix (e.g. "FN_SOURCE_")

        Returns:
            Config instance with values from env vars or defaults
        """
        env_values: Dict[str, Any] = {}

        for key, value in os.environ.items():
            if key.startswith(prefix):
                # Remove prefix and convert to lowercase snake_case
                field_name = key[len(prefix):].lower()

                # Parse value based on type hints
                field = config_cls.model_fields.get(field_name, None)
                if field is not None:
                    type_annotation = field.annotation
                    type_origin = getattr(type_annotation, '__origin__', None)

                    # Handle list[str]
                    # Check for origin class using equality and string check for broader compatibility
                    is_list = (
                        type_origin == list
                        or str(type_annotation).startswith('list[')
                        or str(type_annotation).startswith('List[')
                    )
                    if is_list:
                        value = [v.strip() for v in value.split(',') if v.strip()]
                    elif type_annotation == bool:
                        value = value.lower() in ('true', '1', 'yes', 'on')
                    elif type_annotation == int:
                        value = int(value)
                    elif type_annotation == float:
                        value = float(value)

                env_values[field_name] = value

        # Create config instance with env values (defaults apply for missing fields)
        return config_cls(**env_values)


# Class-level registry (outside the Pydantic model so Pydantic doesn't process them as fields)
MainConfig._source_configs: Dict[str, Type[BaseModel]] = {}
MainConfig._target_configs: Dict[str, Type[BaseModel]] = {}


models_registry = ModelsRegistry()

def get_config() -> MainConfig:
    """Get config instance (always re-read env vars).
    Call this AFTER setting environment variables.
    """
    return MainConfig()

# Convenience access - but prefer get_config() if setting env vars dynamically
config = MainConfig()
