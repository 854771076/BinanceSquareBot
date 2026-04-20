import httpx
from loguru import logger
from typing import Tuple

from binance_square_bot.services.base import BaseTarget


class BinanceTarget(BaseTarget):
    """Binance Square publishing target with multi-API key support."""

    class Config(BaseTarget.Config):
        enabled: bool = True
        daily_max_posts_per_key: int = 100
        api_keys: list[str] = []
        api_url: str = "https://www.binance.com/bapi/composite/v1/public/pgc/openApi/content/add"
        stop_words: list[str] = ["bitget","okx"]

    def __init__(self):
        super().__init__()
        self.client = httpx.Client(timeout=30.0)
        self.stop_words = set(self.config.stop_words)
    
    def is_contains_stop_words(self, content: str) -> bool:
        """Check if content contains any stop words. Case-insensitive."""
        return any(word.lower() in content.lower() for word in self.stop_words)


    def publish(self, content: str, api_key: str) -> Tuple[bool, str]:
        """Publish content using a specific API key.

        Args:
            content: The tweet content to publish
            api_key: The Binance Square OpenAPI key

        Returns:
            Tuple of (success: bool, error_message: str)
        """
        if self.is_contains_stop_words(content):
            logger.info(f"Content '{content[:50]}' contains stop words, skipping publish")
            return False, "Content contains stop words"
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
                self.config.api_url,
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
