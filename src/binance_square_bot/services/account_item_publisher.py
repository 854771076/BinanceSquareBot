import time
from typing import Any

from binance_square_bot.services.generation.deep_agent_generator import (
    DeepAgentTweetGenerator,
)
from binance_square_bot.services.generation.models import TweetSourceItem
from binance_square_bot.services.target.binance_target import mask_api_key


class AccountItemPublisher:
    """Generate and publish account-specific tweets for source items."""

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
        available_keys = [
            api_key
            for api_key in api_keys
            if storage.can_publish_key(
                target_name,
                api_key,
                target.config.daily_max_posts_per_key,
            )
        ]
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
            for account_index, api_key in enumerate(available_keys, start=1):
                api_key_mask = key_masks[api_key]
                try:
                    tweet = self.generator.generate_for_account(
                        item=item,
                        api_key_mask=api_key_mask,
                        account_index=account_index,
                        api_key=api_key,
                    )
                except Exception as exc:
                    stats["generated_failed"] += 1
                    error = _sanitize_message(str(exc), key_masks)
                    print(f"Generation failed for API key {api_key_mask}: {error}")
                    continue

                stats["generated_success"] += 1

                if dry_run:
                    safe_tweet = _sanitize_message(tweet, key_masks)
                    print(f"[DRY RUN] API key {api_key_mask}: {safe_tweet}")
                    continue

                try:
                    filtered_tweet = target.filter(tweet)
                    success, error = target.publish(filtered_tweet, api_key)
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


def _sanitize_message(message: str, key_masks: dict[str, str]) -> str:
    safe_message = message
    for api_key, api_key_mask in key_masks.items():
        safe_message = safe_message.replace(api_key, api_key_mask)
    return safe_message
