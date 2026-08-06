import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from binance_square_bot.services.generation.deep_agent_generator import (
    DeepAgentTweetGenerator,
)
from binance_square_bot.services.generation.models import TweetSourceItem
from binance_square_bot.services.target.binance_target import mask_api_key
from binance_square_bot.services.target.square_post import SquarePost


class AccountItemPublisher:
    """Generate and publish account-specific posts for source items.

    Publishing is parallelized ACROSS API keys (each account is a worker),
    while WITHIN a key items still run serially so the inter-publish delay
    keeps per-account rate limiting intact.
    """

    def __init__(
        self,
        generator: DeepAgentTweetGenerator | None = None,
        delay_between_publishes: float = 1.0,
        max_workers: int = 1,
    ) -> None:
        self.generator = generator or DeepAgentTweetGenerator()
        self.delay_between_publishes = delay_between_publishes
        self.max_workers = max(1, max_workers)

    def publish_items(
        self,
        items: list[TweetSourceItem],
        target: Any,
        api_keys: list[str],
        storage: Any,
        dry_run: bool = False,
    ) -> dict[str, int | bool]:
        target_name = target.__class__.__name__
        stats: dict[str, int | bool] = {
            "items_total": len(items),
            "api_keys_total": len(api_keys),
            "generated_success": 0,
            "generated_failed": 0,
            "published_success": 0,
            "published_failed": 0,
            "dry_run": dry_run,
        }
        if not items or not api_keys:
            return stats

        key_masks = {api_key: mask_api_key(api_key) for api_key in api_keys}
        stats_lock = threading.Lock()

        def bump(field: str, by: int = 1) -> None:
            with stats_lock:
                stats[field] += by  # type: ignore[operator]

        # item.identifier -> whether at least one account published it.
        published_items: set[str] = set()
        published_lock = threading.Lock()

        # account_index is the 1-based position of the key among all keys.
        # It must be stable per key so the LLM gets a distinct variation seed
        # per account for the SAME item (key0 -> 1, key1 -> 2), independent of
        # which keys are quota-available or how workers are scheduled.
        key_order = {key: idx for idx, key in enumerate(api_keys, start=1)}

        def worker(api_key: str) -> None:
            key_mask = key_masks[api_key]
            account_index = key_order[api_key]
            for item in items:
                if not storage.can_publish_key(
                    target_name,
                    api_key,
                    target.config.daily_max_posts_per_key,
                ):
                    continue
                try:
                    generated = self.generator.generate_for_account(
                        item=item,
                        api_key_mask=key_mask,
                        account_index=account_index,
                        api_key=api_key,
                    )
                except Exception as exc:
                    bump("generated_failed")
                    error = _sanitize_message(str(exc), key_masks)
                    print(f"Generation failed for API key {key_mask}: {error}")
                    continue

                if not _passes_rewrite_gate(item, generated.body, key_mask):
                    bump("generated_failed")
                    continue

                bump("generated_success")
                post = _build_square_post(item, generated.body, generated.title)

                try:
                    post.validate_media()
                except ValueError as exc:
                    bump("published_failed")
                    print(f"Skipping item {item.identifier} for {key_mask}: {exc}")
                    continue

                if dry_run:
                    safe_body = _sanitize_message(generated.body, key_masks)
                    title_part = f" | title={generated.title}" if generated.title else ""
                    media_part = _describe_media(item)
                    print(
                        f"[DRY RUN] API key {key_mask}{title_part} "
                        f"[{item.post_type}{media_part}]: {safe_body[:200]}"
                    )
                    continue

                try:
                    filtered_post = target.filter(post)
                    success, error = target.publish(filtered_post, api_key)
                except Exception as exc:
                    bump("published_failed")
                    safe_error = _sanitize_message(str(exc), key_masks)
                    print(f"Publish failed for API key {key_mask}: {safe_error}")
                    continue

                if success:
                    bump("published_success")
                    storage.increment_daily_publish_count(target_name, api_key)
                    with published_lock:
                        published_items.add(item.identifier)
                else:
                    bump("published_failed")
                    safe_error = _sanitize_message(str(error), key_masks)
                    print(f"Publish failed for API key {key_mask}: {safe_error}")

                if self.delay_between_publishes > 0:
                    time.sleep(self.delay_between_publishes)

        # Fan out one worker per available API key.
        worker_count = min(self.max_workers, len(api_keys))
        with ThreadPoolExecutor(max_workers=worker_count) as pool:
            futures = [pool.submit(worker, key) for key in api_keys]
            for fut in as_completed(futures):
                # Surface unexpected worker errors instead of swallowing them.
                fut.result()

        for item in items:
            if item.identifier in published_items:
                storage.mark_content_published(
                    source_name=item.source_name,
                    content_type=item.content_type,
                    content_identifier=item.identifier,
                )

        return stats


def _passes_rewrite_gate(
    item: TweetSourceItem, body: str, key_mask: str
) -> bool:
    """SquareHot rewrites must not be too similar to the original.

    Same-script near-copies are blocked; cross-script (EN original -> CN
    rewrite) pairs always pass because the language shift is itself a
    substantive rewrite.
    """
    if item.source_name != "SquareHotSource" or not item.body:
        return True
    from binance_square_bot.services.rewrite_check import is_too_similar

    threshold = float(item.metadata.get("similarity_threshold", 0.7))
    if is_too_similar(item.body, body, threshold):
        print(
            f"Rewrite too close to original (factual overlap > {threshold}); "
            f"skipping API key {key_mask}"
        )
        return False
    return True


def _build_square_post(
    item: TweetSourceItem, body: str, title: str | None
) -> SquarePost:
    return SquarePost(
        post_type=item.post_type,
        body=body,
        title=title,
        images=list(item.images),
        cover=item.cover,
        video=item.video,
        video_duration=item.video_duration,
    )


def _describe_media(item: TweetSourceItem) -> str:
    if item.post_type == "image":
        return f", {len(item.images)} imgs"
    if item.post_type == "article":
        return ", cover" if item.cover else ""
    if item.post_type == "video":
        return ", video"
    return ""


def _sanitize_message(message: str, key_masks: dict[str, str]) -> str:
    safe_message = message
    for api_key in sorted(key_masks, key=len, reverse=True):
        safe_message = safe_message.replace(api_key, key_masks[api_key])
    return safe_message
