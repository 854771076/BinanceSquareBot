from __future__ import annotations

import time
from typing import Tuple, Union

import httpx
from loguru import logger

from binance_square_bot.services.base import BaseTarget
from binance_square_bot.services.target.binance_media import (
    BASE_URL_V1,
    FATAL_CODES,
    BinanceApi,
    BinanceMediaError,
    probe_video_duration,
)
from binance_square_bot.services.target.square_post import CONTENT_TYPE_MAP, SquarePost


def mask_api_key(api_key: str) -> str:
    """Mask API key for logging - show first 8 chars and last 4 chars."""
    if len(api_key) <= 12:
        return f"{api_key[:4]}...{api_key[-2:]}" if len(api_key) > 6 else "***"
    return f"{api_key[:8]}...{api_key[-4:]}"


PostInput = Union[str, SquarePost]


class BinanceTarget(BaseTarget):
    """Binance Square publishing target with multi-API key support.

    Accepts either a plain string (legacy text-only post) or a SquarePost
    describing a text/image/article/video post.
    """

    class Config(BaseTarget.Config):
        enabled: bool = True
        daily_max_posts_per_key: int = 100
        daily_max_uploads_per_key: int = 400
        api_keys: list[str] = []
        api_url: str = f"{BASE_URL_V1}/content/add"
        stop_words: list[str] = ["bitget", "okx"]
        max_retries: int = 3
        retry_delay: float = 2.0
        upload_poll_interval: float = 3.0
        upload_max_poll_retries: int = 10
        upload_timeout: float = 120.0

    def __init__(self):
        super().__init__()
        self.client = httpx.Client(timeout=httpx.Timeout(self.config.upload_timeout))
        self.stop_words = set(self.config.stop_words)
        self._last_publish_time = 0.0

    def is_contains_stop_words(self, content: str) -> bool:
        """Check if content contains any stop words. Case-insensitive."""
        return any(word.lower() in content.lower() for word in self.stop_words)

    def _contains_stop_words(self, post: SquarePost) -> bool:
        """Check both body and article title for stop words."""
        if self.is_contains_stop_words(post.body):
            return True
        if post.title and self.is_contains_stop_words(post.title):
            return True
        return False

    # ----- public publish entry -----

    def publish(self, content: PostInput, api_key: str) -> Tuple[bool, str]:
        """Publish content. Retries only on retryable/network errors.

        Accepts a string (text post) or SquarePost.
        """
        key_mask = mask_api_key(api_key)
        post = self._coerce_post(content)
        post.validate_media()

        if self._contains_stop_words(post):
            logger.info(
                f"[API:{key_mask}] ⏭️ Skipped - contains stop words: "
                f"{(post.title or post.body)[:40]}..."
            )
            return False, "Content contains stop words"

        # Build the publish body (uploads media) once — uploaded S3 URLs are
        # reusable across publish retries; re-uploading wastes the daily upload quota.
        try:
            body = self._build_publish_body(post, api_key, key_mask)
        except BinanceMediaError as exc:
            # Media errors (fatal OpenAPI codes, processing failures) do not benefit from retry.
            logger.error(f"[API:{key_mask}] ❌ Media upload failed: {exc}")
            return False, str(exc)

        for attempt in range(self.config.max_retries):

            success, error, retryable = self._try_publish_once(body, api_key, key_mask, post)
            if success:
                logger.success(f"[API:{key_mask}] ✅ Published {post.post_type}: {post.body[:40]}...")
                return True, ""

            if retryable and attempt < self.config.max_retries - 1:
                wait = self.config.retry_delay * (attempt + 1)
                logger.warning(
                    f"[API:{key_mask}] ⚠️ Publish failed ({attempt + 1}/{self.config.max_retries}), "
                    f"retrying in {wait}s: {error}"
                )
                time.sleep(wait)
                continue

            logger.error(f"[API:{key_mask}] ❌ Failed after {attempt + 1} attempts: {error}")
            return False, error

        return False, "All retries failed"

    # ----- internals -----

    @staticmethod
    def _coerce_post(content: PostInput) -> SquarePost:
        if isinstance(content, SquarePost):
            return content
        return SquarePost(post_type="text", body=content)

    def _build_publish_body(self, post: SquarePost, api_key: str, key_mask: str) -> dict:
        media = BinanceApi(
            self.client,
            api_key,
            poll_interval=self.config.upload_poll_interval,
            max_poll_retries=self.config.upload_max_poll_retries,
        )
        body: dict = {"contentType": CONTENT_TYPE_MAP[post.post_type], "bodyTextOnly": post.body}

        if post.post_type == "image":
            logger.debug(f"[API:{key_mask}] 🖼️ Uploading {len(post.images)} images")
            body["imageList"] = [media.upload_image(p) for p in post.images]
        elif post.post_type == "article":
            assert post.title and post.cover
            logger.debug(f"[API:{key_mask}] 📝 Uploading article cover")
            body["title"] = post.title
            body["cover"] = media.upload_image(post.cover)
        elif post.post_type == "video":
            assert post.video
            duration = post.video_duration
            if duration is None:
                duration = probe_video_duration(post.video)
            logger.debug(f"[API:{key_mask}] 🎬 Uploading video (duration={duration}s)")
            file_ticket, cover_url = media.upload_video(post.video)
            body.update(
                {
                    "fileTicket": file_ticket,
                    "cover": cover_url,
                    "videoTimeSeconds": float(duration),
                    "isPublish": True,
                }
            )
        return body

    def _try_publish_once(
        self, body: dict, api_key: str, key_mask: str, post: SquarePost
    ) -> Tuple[bool, str, bool]:
        headers = {
            "X-Square-OpenAPI-Key": api_key,
            "Content-Type": "application/json",
            "clienttype": "binanceSkill",
        }
        try:
            response = self.client.post(self.config.api_url, headers=headers, json=body)
            if response.status_code == 504:
                # Reference skill: treat as success — submission landed but gateway timed out.
                logger.warning(f"[API:{key_mask}] ⚠️ 504 after submit — treating as success (no post id)")
                return True, "", False
            response.raise_for_status()
            data = response.json()
            code = str(data.get("code"))
            message = data.get("message", "")
            if code in ("000000", "0"):
                return True, "", False
            if code in FATAL_CODES:
                return False, message or f"API error code: {code}", False
            # Unknown codes — retry if message smells transient.
            retryable = code == "10004" or "network" in message.lower() or "timeout" in message.lower()
            return False, message or f"API error code: {code}", retryable
        except (httpx.HTTPError, httpx.TimeoutException) as e:
            return False, f"HTTP:{e}", True
        except Exception as e:  # noqa: BLE001 - surface unexpected errors, don't retry blindly
            return False, f"Unexpected: {e}", False
