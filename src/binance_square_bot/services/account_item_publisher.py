import time
from typing import Any

from binance_square_bot.services.generation.deep_agent_generator import (
    DeepAgentTweetGenerator,
)
from binance_square_bot.services.generation.models import TweetSourceItem
from binance_square_bot.services.target.binance_target import mask_api_key
from binance_square_bot.services.target.square_post import SquarePost


class AccountItemPublisher:
    """Generate and publish account-specific posts for source items."""

    def __init__(
        self,
        generator: DeepAgentTweetGenerator | None = None,
        delay_between_publishes: float = 1.0,
    ) -> None:
        self.generator = generator or DeepAgentTweetGenerator()
        self.delay_between_publishes = delay_between_publishes

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
        key_masks = {api_key: mask_api_key(api_key) for api_key in api_keys}

        for item in items:
            item_success = False
            available_account_index = 0
            for api_key in api_keys:
                if not storage.can_publish_key(
                    target_name,
                    api_key,
                    target.config.daily_max_posts_per_key,
                ):
                    continue

                available_account_index += 1
                api_key_mask = key_masks[api_key]
                try:
                    generated = self.generator.generate_for_account(
                        item=item,
                        api_key_mask=api_key_mask,
                        account_index=available_account_index,
                        api_key=api_key,
                    )
                except Exception as exc:
                    stats["generated_failed"] += 1
                    error = _sanitize_message(str(exc), key_masks)
                    print(f"Generation failed for API key {api_key_mask}: {error}")
                    continue

                # SquareHot rewrite gate — cross-language safe. String similarity
                # is meaningless for EN->CN rewrites, so compare factual fingerprints
                # (numbers, $TICKERS, #hashtags, URLs, proper nouns) instead.
                if item.source_name == "SquareHotSource" and item.body:
                    from binance_square_bot.services.rewrite_check import is_too_similar

                    threshold = float(item.metadata.get("similarity_threshold", 0.7))
                    if is_too_similar(item.body, generated.body, threshold):
                        stats["generated_failed"] += 1
                        print(
                            f"Rewrite too close to original (factual overlap > {threshold}); "
                            f"skipping API key {api_key_mask}"
                        )
                        continue

                stats["generated_success"] += 1

                post = _build_square_post(item, generated.body, generated.title)

                # Articles require a cover (Square API rule). If image
                # attribution couldn't find one, skip rather than crash on
                # validate_media().
                try:
                    post.validate_media()
                except ValueError as exc:
                    stats["published_failed"] += 1
                    print(
                        f"Skipping item {item.identifier} for {api_key_mask}: {exc}"
                    )
                    continue

                if dry_run:
                    safe_body = _sanitize_message(generated.body, key_masks)
                    title_part = f" | title={generated.title}" if generated.title else ""
                    media_part = _describe_media(item)
                    print(
                        f"[DRY RUN] API key {api_key_mask}{title_part} "
                        f"[{item.post_type}{media_part}]: {safe_body[:200]}"
                    )
                    continue

                try:
                    filtered_post = target.filter(post)
                    success, error = target.publish(filtered_post, api_key)
                except Exception as exc:
                    stats["published_failed"] += 1
                    safe_error = _sanitize_message(str(exc), key_masks)
                    print(f"Publish failed for API key {api_key_mask}: {safe_error}")
                    continue

                if success:
                    stats["published_success"] += 1
                    storage.increment_daily_publish_count(target_name, api_key)
                    item_success = True
                else:
                    stats["published_failed"] += 1
                    safe_error = _sanitize_message(str(error), key_masks)
                    print(f"Publish failed for API key {api_key_mask}: {safe_error}")

                if self.delay_between_publishes > 0:
                    time.sleep(self.delay_between_publishes)

            if item_success:
                storage.mark_content_published(
                    source_name=item.source_name,
                    content_type=item.content_type,
                    content_identifier=item.identifier,
                )

        return stats


def _build_square_post(item: TweetSourceItem, body: str, title: str | None) -> SquarePost:
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
