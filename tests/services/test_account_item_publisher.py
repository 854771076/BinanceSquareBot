from dataclasses import dataclass

from binance_square_bot.services.account_item_publisher import AccountItemPublisher
from binance_square_bot.services.generation.models import TweetSourceItem
from binance_square_bot.services.target.binance_target import mask_api_key


class FakeGenerator:
    def __init__(self, outputs=None, failures=None, failure_messages=None):
        self.outputs = outputs or {}
        self.failures = failures or set()
        self.failure_messages = failure_messages or {}
        self.calls = []

    def generate_for_account(self, *, item, api_key_mask, account_index, api_key):
        self.calls.append(
            {
                "item": item,
                "api_key_mask": api_key_mask,
                "account_index": account_index,
                "api_key": api_key,
            }
        )
        key = (item.identifier, api_key)
        if key in self.failures:
            message = self.failure_messages.get(key, f"generation failed for {api_key_mask}")
            raise ValueError(message)
        return self.outputs.get(key, f"tweet-{item.identifier}-{account_index}")


class FakeStorage:
    def __init__(self, unavailable_keys=None):
        self.unavailable_keys = set(unavailable_keys or [])
        self.can_publish_key_calls = []
        self.increment_calls = []
        self.mark_calls = []

    def can_publish_key(self, target_name, api_key, max_posts):
        self.can_publish_key_calls.append((target_name, api_key, max_posts))
        return api_key not in self.unavailable_keys

    def increment_daily_publish_count(self, target_name, api_key):
        self.increment_calls.append((target_name, api_key))

    def mark_content_published(self, *, source_name, content_type, content_identifier):
        self.mark_calls.append(
            {
                "source_name": source_name,
                "content_type": content_type,
                "content_identifier": content_identifier,
            }
        )


class FakeTarget:
    @dataclass
    class Config:
        daily_max_posts_per_key: int = 3

    def __init__(self, failures=None):
        self.config = self.Config()
        self.failures = set(failures or [])
        self.filter_calls = []
        self.publish_calls = []

    def filter(self, tweet):
        self.filter_calls.append(tweet)
        return f"filtered:{tweet}"

    def publish(self, tweet, api_key):
        self.publish_calls.append((tweet, api_key))
        if (tweet, api_key) in self.failures or api_key in self.failures:
            return False, "publish failed"
        return True, ""



def make_item(identifier="item-1"):
    return TweetSourceItem(
        source_name="FnSource",
        content_type="news",
        identifier=identifier,
        title=f"Title {identifier}",
        summary=f"Summary {identifier}",
    )


def test_publishes_every_item_to_every_available_key_and_marks_each_item():
    items = [make_item("item-1"), make_item("item-2")]
    api_keys = ["KEY_ONE_SECRET_1234", "KEY_TWO_SECRET_5678"]
    generator = FakeGenerator()
    target = FakeTarget()
    storage = FakeStorage()
    publisher = AccountItemPublisher(generator=generator, delay_between_publishes=0)

    stats = publisher.publish_items(items, target, api_keys, storage)

    assert stats == {
        "items_total": 2,
        "api_keys_total": 2,
        "generated_success": 4,
        "generated_failed": 0,
        "published_success": 4,
        "published_failed": 0,
        "dry_run": False,
    }
    assert len(generator.calls) == 4
    assert [call["item"].identifier for call in generator.calls] == [
        "item-1",
        "item-1",
        "item-2",
        "item-2",
    ]
    assert [call["api_key"] for call in generator.calls] == [
        api_keys[0],
        api_keys[1],
        api_keys[0],
        api_keys[1],
    ]
    assert [call["api_key_mask"] for call in generator.calls] == [
        mask_api_key(api_keys[0]),
        mask_api_key(api_keys[1]),
        mask_api_key(api_keys[0]),
        mask_api_key(api_keys[1]),
    ]
    assert [call["account_index"] for call in generator.calls] == [1, 2, 1, 2]
    assert target.publish_calls == [
        ("filtered:tweet-item-1-1", api_keys[0]),
        ("filtered:tweet-item-1-2", api_keys[1]),
        ("filtered:tweet-item-2-1", api_keys[0]),
        ("filtered:tweet-item-2-2", api_keys[1]),
    ]
    assert storage.increment_calls == [
        ("FakeTarget", api_keys[0]),
        ("FakeTarget", api_keys[1]),
        ("FakeTarget", api_keys[0]),
        ("FakeTarget", api_keys[1]),
    ]
    assert storage.mark_calls == [
        {
            "source_name": "FnSource",
            "content_type": "news",
            "content_identifier": "item-1",
        },
        {
            "source_name": "FnSource",
            "content_type": "news",
            "content_identifier": "item-2",
        },
    ]


def test_marks_item_when_at_least_one_account_publish_succeeds():
    item = make_item("partial-success")
    api_keys = ["KEY_ONE_SECRET_1234", "KEY_TWO_SECRET_5678"]
    generator = FakeGenerator()
    target = FakeTarget(failures={"KEY_ONE_SECRET_1234"})
    storage = FakeStorage()
    publisher = AccountItemPublisher(generator=generator, delay_between_publishes=0)

    stats = publisher.publish_items([item], target, api_keys, storage)

    assert stats["published_success"] == 1
    assert stats["published_failed"] == 1
    assert storage.mark_calls == [
        {
            "source_name": "FnSource",
            "content_type": "news",
            "content_identifier": "partial-success",
        }
    ]


def test_does_not_mark_item_when_all_account_publishes_fail():
    item = make_item("all-fail")
    api_keys = ["KEY_ONE_SECRET_1234", "KEY_TWO_SECRET_5678"]
    generator = FakeGenerator()
    target = FakeTarget(failures=set(api_keys))
    storage = FakeStorage()
    publisher = AccountItemPublisher(generator=generator, delay_between_publishes=0)

    stats = publisher.publish_items([item], target, api_keys, storage)

    assert stats["published_success"] == 0
    assert stats["published_failed"] == 2
    assert storage.increment_calls == []
    assert storage.mark_calls == []


def test_dry_run_generates_but_does_not_publish_increment_or_mark(capsys):
    item = make_item("dry-run")
    api_key = "FULL_SECRET_API_KEY_9999"
    generator = FakeGenerator(outputs={("dry-run", api_key): "dry run tweet"})
    target = FakeTarget()
    storage = FakeStorage()
    publisher = AccountItemPublisher(generator=generator, delay_between_publishes=0)

    stats = publisher.publish_items([item], target, [api_key], storage, dry_run=True)

    assert stats == {
        "items_total": 1,
        "api_keys_total": 1,
        "generated_success": 1,
        "generated_failed": 0,
        "published_success": 0,
        "published_failed": 0,
        "dry_run": True,
    }
    assert len(generator.calls) == 1
    assert target.filter_calls == []
    assert target.publish_calls == []
    assert storage.increment_calls == []
    assert storage.mark_calls == []
    output = capsys.readouterr().out
    assert mask_api_key(api_key) in output
    assert "dry run tweet" in output
    assert api_key not in output


def test_skips_unavailable_keys_for_generation_and_publishing():
    item = make_item("available-only")
    api_keys = ["KEY_ONE_SECRET_1234", "KEY_TWO_SECRET_5678"]
    generator = FakeGenerator()
    target = FakeTarget()
    storage = FakeStorage(unavailable_keys={api_keys[0]})
    publisher = AccountItemPublisher(generator=generator, delay_between_publishes=0)

    stats = publisher.publish_items([item], target, api_keys, storage)

    assert stats["api_keys_total"] == 2
    assert stats["generated_success"] == 1
    assert stats["published_success"] == 1
    assert storage.can_publish_key_calls == [
        ("FakeTarget", api_keys[0], 3),
        ("FakeTarget", api_keys[1], 3),
    ]
    assert [call["api_key"] for call in generator.calls] == [api_keys[1]]
    assert [call["account_index"] for call in generator.calls] == [1]
    assert target.publish_calls == [("filtered:tweet-available-only-1", api_keys[1])]


def test_generation_failure_for_one_key_continues_other_accounts():
    item = make_item("generation-failure")
    api_keys = ["KEY_ONE_SECRET_1234", "KEY_TWO_SECRET_5678"]
    generator = FakeGenerator(failures={("generation-failure", api_keys[0])})
    target = FakeTarget()
    storage = FakeStorage()
    publisher = AccountItemPublisher(generator=generator, delay_between_publishes=0)

    stats = publisher.publish_items([item], target, api_keys, storage)

    assert stats["generated_success"] == 1
    assert stats["generated_failed"] == 1
    assert stats["published_success"] == 1
    assert stats["published_failed"] == 0
    assert len(generator.calls) == 2
    assert target.publish_calls == [("filtered:tweet-generation-failure-2", api_keys[1])]
    assert storage.increment_calls == [("FakeTarget", api_keys[1])]
    assert storage.mark_calls == [
        {
            "source_name": "FnSource",
            "content_type": "news",
            "content_identifier": "generation-failure",
        }
    ]


def test_generation_failure_output_does_not_leak_full_api_key(capsys):
    item = make_item("secret-failure")
    api_key = "FULL_SECRET_API_KEY_9999"
    generator = FakeGenerator(
        failures={("secret-failure", api_key)},
        failure_messages={
            ("secret-failure", api_key): f"provider rejected {api_key}",
        },
    )
    target = FakeTarget()
    storage = FakeStorage()
    publisher = AccountItemPublisher(generator=generator, delay_between_publishes=0)

    stats = publisher.publish_items([item], target, [api_key], storage)

    output = capsys.readouterr().out
    assert stats["generated_failed"] == 1
    assert mask_api_key(api_key) in output
    assert api_key not in output
