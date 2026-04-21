import httpx
import time
from loguru import logger
from typing import Tuple

from binance_square_bot.services.base import BaseTarget


def mask_api_key(api_key: str) -> str:
    """Mask API key for logging - show first 8 chars and last 4 chars."""
    if len(api_key) <= 12:
        return f"{api_key[:4]}...{api_key[-2:]}" if len(api_key) > 6 else "***"
    return f"{api_key[:8]}...{api_key[-4:]}"


class BinanceTarget(BaseTarget):
    """Binance Square publishing target with multi-API key support."""

    class Config(BaseTarget.Config):
        enabled: bool = True
        daily_max_posts_per_key: int = 100
        api_keys: list[str] = []
        api_url: str = "https://www.binance.com/bapi/composite/v1/public/pgc/openApi/content/add"
        stop_words: list[str] = ["bitget","okx"]
        max_retries: int = 3  # 发布失败重试次数
        retry_delay: float = 2.0  # 重试间隔（秒）

    def __init__(self):
        super().__init__()
        self.client = httpx.Client(timeout=30.0)
        self.stop_words = set(self.config.stop_words)
        self._last_publish_time = 0.0

    def is_contains_stop_words(self, content: str) -> bool:
        """Check if content contains any stop words. Case-insensitive."""
        return any(word.lower() in content.lower() for word in self.stop_words)

    def _try_publish_once(self, content: str, api_key: str, key_mask: str = "") -> Tuple[bool, str]:
        """Try to publish once - returns (success, error_message)."""
        headers = {
            "X-Square-OpenAPI-Key": api_key,
            "Content-Type": "application/json",
            "clienttype": "binanceSkill",
        }

        body = {
            "bodyTextOnly": content,
        }

        try:
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
                return True, ""
            else:
                # Retryable errors: network errors, timeouts, etc.
                if code == 10004 or "network" in message.lower() or "timeout" in message.lower():
                    return False, f"RETRYABLE:{message}"
                return False, message or f"API error code: {code}"

        except (httpx.HTTPError, httpx.TimeoutException) as e:
            return False, f"RETRYABLE:HTTP:{str(e)}"
        except Exception as e:
            return False, f"Unexpected error: {str(e)}"

    def publish(self, content: str, api_key: str) -> Tuple[bool, str]:
        """Publish content using a specific API key with retry logic.

        Args:
            content: The tweet content to publish
            api_key: The Binance Square OpenAPI key

        Returns:
            Tuple of (success: bool, error_message: str)
        """
        key_mask = mask_api_key(api_key)

        if self.is_contains_stop_words(content):
            logger.info(f"[API:{key_mask}] ⏭️ Skipped - contains stop words: {content[:40]}...")
            return False, "Content contains stop words"

        logger.debug(f"[API:{key_mask}] 📤 Publishing: {content[:50]}...")

        for attempt in range(self.config.max_retries):
            success, error = self._try_publish_once(content, api_key, key_mask)

            if success:
                logger.success(f"[API:{key_mask}] ✅ Published: {content[:40]}...")
                return True, ""

            # Check if this is a retryable error
            is_retryable = error.startswith("RETRYABLE:")
            clean_error = error.replace("RETRYABLE:", "")

            if is_retryable and attempt < self.config.max_retries - 1:
                wait_time = self.config.retry_delay * (attempt + 1)
                logger.warning(
                    f"[API:{key_mask}] ⚠️ Publish failed (attempt {attempt + 1}/{self.config.max_retries}), "
                    f"retrying in {wait_time}s: {clean_error}"
                )
                time.sleep(wait_time)
                continue

            # Final attempt or non-retryable error
            logger.error(f"[API:{key_mask}] ❌ Failed after {attempt + 1} attempts: {clean_error}")
            return False, clean_error

        # Should never reach here, but just in case
        logger.error(f"[API:{key_mask}] ❌ All {self.config.max_retries} attempts failed")
        return False, "All retries failed"
