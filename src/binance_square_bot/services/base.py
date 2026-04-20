from pydantic import BaseModel
from abc import ABC, abstractmethod
from typing import Type, Optional, Any
from loguru import logger

# Late import to avoid circular import
def _get_config():
    from binance_square_bot.config import get_config
    return get_config()


class BaseSource(ABC):
    """Base class for all data sources.

    Each Source implements: config definition + data model + data fetch + content generation.

    Environment variable naming: {SOURCE_NAME}_{FIELD_NAME}
    Example: FN_SOURCE_ENABLED, POLYMARKET_SOURCE_HOST
    """

    # Subclasses should define their own Pydantic model
    Model: Optional[Type[BaseModel]] = None

    class Config(BaseModel):
        """Base configuration for all sources."""
        enabled: bool = True
        daily_max_executions: int = 1

    def __init_subclass__(cls, **kwargs):
        """Auto-register config class when subclass is defined."""
        super().__init_subclass__(**kwargs)
        from binance_square_bot.config import MainConfig
        MainConfig.register_source_config(cls.__name__, cls.Config)
        logger.debug(f"Auto-registered source config: {cls.__name__}")

    def __init__(self):
        """Initialize source with config loaded from environment variables."""
        self.name = self.__class__.__name__
        self.config = _get_config().get_source_config(self.name)
        if self.config is None:
            logger.warning(f"No config registered for {self.name}, using defaults")
            self.config = self.Config()
        logger.debug(f"{self.name} loaded config: {self.config.model_dump()}")

    @abstractmethod
    def fetch(self) -> Any:
        """Fetch data from source. Returns Model instance(s)."""
        pass

    @abstractmethod
    def generate(self, data: Any) -> Any:
        """Generate content from fetched data."""
        pass


class BaseTarget(ABC):
    """Base class for all publish targets.

    Environment variable naming: {TARGET_NAME}_{FIELD_NAME}
    Example: BINANCE_TARGET_API_KEYS=key1,key2
    """

    class Config(BaseModel):
        """Base configuration for all targets."""
        enabled: bool = True
        daily_max_posts_per_key: int = 100
        api_keys: list[str] = []

    def __init_subclass__(cls, **kwargs):
        """Auto-register config class when subclass is defined."""
        super().__init_subclass__(**kwargs)
        from binance_square_bot.config import MainConfig
        MainConfig.register_target_config(cls.__name__, cls.Config)
        logger.debug(f"Auto-registered target config: {cls.__name__}")

    def __init__(self):
        """Initialize target with config loaded from environment variables."""
        self.name = self.__class__.__name__
        self.config = _get_config().get_target_config(self.name)
        if self.config is None:
            logger.warning(f"No config registered for {self.name}, using defaults")
            self.config = self.Config()
        logger.debug(f"{self.name} loaded config: {self.config.model_dump()}")

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
