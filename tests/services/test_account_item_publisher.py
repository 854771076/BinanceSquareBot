from dataclasses import dataclass

from binance_square_bot.services.account_item_publisher import AccountItemPublisher
from binance_square_bot.services.generation.deep_agent_generator import GeneratedPost
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
            message = self.failure_messages.get(
                key,
                f"generation failed for {api_key_mask}",
            )
            raise ValueError(message)
        body = self.outputs.get(key, f"tweet-{item.identifier}-{account_index}")
        return GeneratedPost(body=body)


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

    def __init__(
        self,
        failures=None,
        failure_messages=None,
        filter_exceptions=None,
        publish_exceptions=None,
    ):
        self.config = self.Config()
        self.failures = set(failures or [])
        self.failure_messages = failure_messages or {}
        self.filter_exceptions = filter_exceptions or {}
        self.publish_exceptions = publish_exceptions or {}
        self.filter_calls = []
        self.publish_calls = []

    def filter(self, post):
        self.filter_calls.append(post)
        if post.body in self.filter_exceptions:
            raise ValueError(self.filter_exceptions[post.body])
        filtered = post.model_copy(update={"body": f"filtered:{post.body}"})
        return filtered

    def publish(self, post, api_key):
        self.publish_calls.append((post, api_key))
        key = (post.body, api_key)
        if key in self.publish_exceptions:
            raise RuntimeError(self.publish_exceptions[key])
        if key in self.failures or (post.body, api_key) in self.failures or api_key in self.failures:
            return False, self.failure_messages.get(key, "publish failed")
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
    assert [(c[0].body, c[1]) for c in target.publish_calls] == [
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
    assert target.publish_calls[0][0].body == "filtered:tweet-available-only-1"
    assert target.publish_calls[0][1] == api_keys[1]


def test_rechecks_key_quota_before_each_item_generation_attempt():
    items = [make_item("first-item"), make_item("second-item")]
    api_key = "KEY_ONE_SECRET_1234"
    generator = FakeGenerator()
    target = FakeTarget()
    storage = FakeStorage()

    def can_publish_until_first_success(target_name, api_key_value, max_posts):
        storage.can_publish_key_calls.append((target_name, api_key_value, max_posts))
        return not storage.increment_calls

    storage.can_publish_key = can_publish_until_first_success
    publisher = AccountItemPublisher(generator=generator, delay_between_publishes=0)

    stats = publisher.publish_items(items, target, [api_key], storage)

    assert stats["generated_success"] == 1
    assert stats["published_success"] == 1
    assert [call["item"].identifier for call in generator.calls] == ["first-item"]
    assert [(c[0].body, c[1]) for c in target.publish_calls] == [("filtered:tweet-first-item-1", api_key)]
    assert storage.can_publish_key_calls == [
        ("FakeTarget", api_key, 3),
        ("FakeTarget", api_key, 3),
    ]
    assert storage.increment_calls == [("FakeTarget", api_key)]
    assert storage.mark_calls == [
        {
            "source_name": "FnSource",
            "content_type": "news",
            "content_identifier": "first-item",
        }
    ]


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
    assert [c[0].body for c in target.publish_calls] == ["filtered:tweet-generation-failure-2"]
    assert [c[1] for c in target.publish_calls] == [api_keys[1]]
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


def test_generation_failure_redacts_overlapping_api_keys_longest_first(capsys):
    item = make_item("overlap-secret-failure")
    api_keys = ["PREFIX_KEY", "PREFIX_KEY_WITH_EXTRA_SECRET"]
    leaked_key = api_keys[1]
    generator = FakeGenerator(
        failures={("overlap-secret-failure", leaked_key)},
        failure_messages={
            ("overlap-secret-failure", leaked_key): f"provider rejected {leaked_key}",
        },
    )
    target = FakeTarget()
    storage = FakeStorage(unavailable_keys={api_keys[0]})
    publisher = AccountItemPublisher(generator=generator, delay_between_publishes=0)

    stats = publisher.publish_items([item], target, api_keys, storage)

    output = capsys.readouterr().out
    assert stats["generated_failed"] == 1
    assert mask_api_key(leaked_key) in output
    assert leaked_key not in output
    assert "WITH_EXTRA_SECRET" not in output


def test_publish_failure_output_does_not_leak_full_api_key(capsys):
    item = make_item("publish-secret-failure")
    api_key = "FULL_SECRET_API_KEY_9999"
    generator = FakeGenerator()
    target = FakeTarget(
        failures={api_key},
        failure_messages={
            ("filtered:tweet-publish-secret-failure-1", api_key): (
                f"publisher rejected {api_key}"
            ),
        },
    )
    storage = FakeStorage()
    publisher = AccountItemPublisher(generator=generator, delay_between_publishes=0)

    stats = publisher.publish_items([item], target, [api_key], storage)

    output = capsys.readouterr().out
    assert stats["published_failed"] == 1
    assert mask_api_key(api_key) in output
    assert api_key not in output


def test_filter_exception_increments_publish_failed_continues_and_masks_key(capsys):
    item = make_item("filter-exception")
    api_keys = ["FULL_SECRET_API_KEY_9999", "SECOND_SECRET_API_KEY_8888"]
    generator = FakeGenerator()
    target = FakeTarget(
        filter_exceptions={
            "tweet-filter-exception-1": f"filter rejected {api_keys[0]}",
        },
    )
    storage = FakeStorage()
    publisher = AccountItemPublisher(generator=generator, delay_between_publishes=0)

    stats = publisher.publish_items([item], target, api_keys, storage)

    output = capsys.readouterr().out
    assert stats["generated_success"] == 2
    assert stats["published_success"] == 1
    assert stats["published_failed"] == 1
    assert target.publish_calls[0][0].body == "filtered:tweet-filter-exception-2"
    assert target.publish_calls[0][1] == api_keys[1]
    assert storage.increment_calls == [("FakeTarget", api_keys[1])]
    assert storage.mark_calls == [
        {
            "source_name": "FnSource",
            "content_type": "news",
            "content_identifier": "filter-exception",
        }
    ]
    assert mask_api_key(api_keys[0]) in output
    assert api_keys[0] not in output


def test_publish_exception_increments_publish_failed_continues_and_masks_key(capsys):
    item = make_item("publish-exception")
    api_keys = ["FULL_SECRET_API_KEY_9999", "SECOND_SECRET_API_KEY_8888"]
    generator = FakeGenerator()
    target = FakeTarget(
        publish_exceptions={
            ("filtered:tweet-publish-exception-1", api_keys[0]): (
                f"publish exploded for {api_keys[0]}"
            ),
        },
    )
    storage = FakeStorage()
    publisher = AccountItemPublisher(generator=generator, delay_between_publishes=0)

    stats = publisher.publish_items([item], target, api_keys, storage)

    output = capsys.readouterr().out
    assert stats["generated_success"] == 2
    assert stats["published_success"] == 1
    assert stats["published_failed"] == 1
    assert [(c[0].body, c[1]) for c in target.publish_calls] == [
        ("filtered:tweet-publish-exception-1", api_keys[0]),
        ("filtered:tweet-publish-exception-2", api_keys[1]),
    ]
    assert storage.increment_calls == [("FakeTarget", api_keys[1])]
    assert storage.mark_calls == [
        {
            "source_name": "FnSource",
            "content_type": "news",
            "content_identifier": "publish-exception",
        }
    ]
    assert mask_api_key(api_keys[0]) in output
    assert api_keys[0] not in output


def test_dry_run_output_redacts_full_api_key_from_generated_tweet(capsys):
    item = make_item("dry-run-secret")
    api_key = "FULL_SECRET_API_KEY_9999"
    generator = FakeGenerator(
        outputs={
            ("dry-run-secret", api_key): f"tweet accidentally includes {api_key}",
        },
    )
    target = FakeTarget()
    storage = FakeStorage()
    publisher = AccountItemPublisher(generator=generator, delay_between_publishes=0)

    stats = publisher.publish_items([item], target, [api_key], storage, dry_run=True)

    output = capsys.readouterr().out
    assert stats["generated_success"] == 1
    assert mask_api_key(api_key) in output
    assert "tweet accidentally includes" in output
    assert api_key not in output
