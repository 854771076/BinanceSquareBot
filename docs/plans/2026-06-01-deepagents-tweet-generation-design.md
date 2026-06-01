# DeepAgents Tweet Generation Migration Design

Date: 2026-06-01

## Goal

Replace the current scattered LangChain/LangGraph-style tweet generation path with DeepAgents, move long writing prompts into reusable repository skills, and change publishing semantics so every Binance account generates and publishes its own distinct tweet for every selected content item.

## Selected approach

Use a two-stage workflow:

1. Sources fetch and normalize content items.
2. Publishing generates account-specific tweet text immediately before publishing each `(content item, API key)` pair.

This replaces the current behavior where source workflows generate one tweet per item and the parallel publisher assigns each content item to exactly one API key.

## Architecture

### New components

- `DeepAgentTweetGenerator`: a unified generation service responsible for selecting a skill, invoking DeepAgents, extracting final text, validating output, and retrying with validation feedback.
- `TweetSourceItem`: a normalized model for publishable content from all sources.
- `TweetContentValidator`: shared output validation for length, hashtag count, token mention count, empty output, and wrapper text.
- Repository skills under `agent_skills/`, one skill directory per content type.

### Skill layout

```text
agent_skills/
├── fn_news/SKILL.md
├── fn_calendar/SKILL.md
├── fn_airdrop/SKILL.md
├── fn_fundraising/SKILL.md
├── followin_topics/SKILL.md
├── followin_token/SKILL.md
└── polymarket_research/SKILL.md
```

Each skill contains stable writing guidance: role, structure, constraints, forbidden patterns, Binance Square output rules, and retry correction instructions. Python code chooses the skill and passes structured content data; source files no longer own large prompt strings.

### Source responsibilities

`FnSource`, `FollowinSource`, and `PolymarketSource` continue to fetch, parse, and filter external data. Their generation role is reduced or routed through the shared DeepAgents generator. Each source workflow converts raw source models into `TweetSourceItem` values with stable metadata:

- `source_name`
- `content_type`
- `identifier`
- `title`
- `summary`
- optional `url`
- optional `metadata`

### Publishing responsibilities

The publish layer changes from content-level distribution to account-level generation:

```text
for item in selected_items:
    for api_key in available_api_keys:
        tweet = generator.generate_for_account(item, masked_api_key/account_index)
        publish tweet with that api_key
```

The full API key is never sent to DeepAgents. Only a masked key or account ordinal may be included to help create account-specific variation.

## Data flow

1. A CLI service fetches source data.
2. Storage filters items already published today by `source_name`, `content_type`, and `identifier`.
3. Parallel workflow aggregates all enabled source items.
4. `total_per_run` limits the number of content items, not account-level tweets.
5. The publisher enumerates all selected content items and all currently available API keys.
6. For each pair, DeepAgents generates a fresh account-specific tweet using the relevant skill.
7. The generated tweet is validated and filtered.
8. A successful publish increments the daily publish count for that API key.
9. If at least one account successfully publishes an item, storage marks the content item as published for the day.
10. If all accounts fail for an item, the item is not marked as published and may be retried later.

## De-duplication semantics

Current behavior: a content item is published by exactly one API key to avoid repeated articles.

New behavior: a content item may be published by every available API key, but each account gets an independently generated tweet.

`identifier` still deduplicates duplicate source candidates. It no longer prevents multiple accounts from publishing the same underlying news item in the same run.

## Generation and validation

`DeepAgentTweetGenerator.generate_for_account()` should:

1. Select the skill from `source_name` and `content_type`.
2. Build a structured user task with content fields, account mask/ordinal, and any retry feedback.
3. Invoke `create_deep_agent()` from DeepAgents with the configured OpenAI-compatible model.
4. Extract the final message text.
5. Validate output.
6. Retry up to `MAX_RETRIES` with validation errors included.
7. Raise a generation failure if all attempts fail.

Shared validation rules:

- Length between `MIN_CHARS` and `MAX_CHARS` by default.
- `#` count no more than `MAX_HASHTAGS`.
- `$` count no more than `MAX_MENTIONS`.
- Output is not empty.
- Output is the tweet body only, not Markdown fences or explanatory wrappers.
- Publishing still applies `BinanceTarget.filter()` for stop words.

Polymarket can keep its research-style longer guidance in the `polymarket_research` skill. If needed, the generator may support content-type-specific validation overrides later.

## Dry-run behavior

`--dry-run` should still call DeepAgents so operators can inspect account-specific outputs. It must not call `BinanceTarget.publish()` or increment counters. Output should group results by content item and masked API key.

Example:

```text
News 1
  API key abcdef12...3456 -> generated tweet A
  API key 12345678...abcd -> generated tweet B
```

## Error handling

- DeepAgents generation failure for one account does not block other accounts for the same item.
- Publish failure for one account does not block other accounts for the same item.
- Publish counters are incremented only after successful publish.
- Content is marked published only if at least one account succeeds.
- Full API keys must not appear in prompts, logs, dry-run output, or exceptions.

## Testing plan

Unit tests should cover:

- Skill selection for each source/content type.
- Conversion from existing source models to `TweetSourceItem`.
- DeepAgents generator success, validation retry, final failure, and API-key masking.
- Account-level publishing: `N items × M keys` calls generation `N*M` times.
- Per-key publish counter increments.
- Content marking only after at least one successful account publish.
- Dry-run generates account-level tweets but does not publish.

Regression tests should update old expectations that each tweet is assigned to one key. New expected behavior is one independently generated tweet per selected content item per available API key.

## Dependency changes

Add `deepagents` to project dependencies. Keep existing LangChain/OpenAI-compatible dependencies as needed by DeepAgents and the current model configuration. Remove direct source-level `ChatOpenAI.invoke()` generation paths where practical.
