# CLAUDE.md

This file provides guidance to Claude Code when working in this repository.

## Common commands

### Setup

```bash
pip install -e .
poetry install
cp .env_example .env
```

### Test, lint, and type-check

```bash
python -m pytest tests/ -v
python -m pytest tests/services/generation/test_deep_agent_generator.py -v
ruff check src/ tests/
ruff format src/ tests/
mypy src/
```

### Run the bot locally

```bash
binance-square-bot --help
binance-square-bot run --dry-run
binance-square-bot calendar --dry-run
binance-square-bot airdrop --dry-run
binance-square-bot fundraising --dry-run
binance-square-bot polymarket-research scan --top-n 5
binance-square-bot polymarket-research run --dry-run
binance-square-bot followin topics --dry-run
binance-square-bot followin io-flow --dry-run
binance-square-bot followin discussion --dry-run
binance-square-bot followin run --dry-run
binance-square-bot parallel --dry-run
binance-square-bot parallel --workers 10 --total-per-run 25
```

`parallel --total-per-run` limits selected content items, not the final per-account tweet count.

## Configuration and runtime state

- Runtime configuration is loaded by `MainConfig` from environment variables and `.env` in `src/binance_square_bot/config.py`.
- Source/target-specific environment variables follow `{CLASS_NAME_AS_UPPER_SNAKE}_{FIELD_NAME}`, for example `FN_SOURCE_DAILY_MAX_EXECUTIONS`, `FOLLOWIN_SOURCE_TIMEOUT`, and `BINANCE_TARGET_API_KEYS`.
- `.env_example` is the current reference for local environment variables. `BINANCE_TARGET_API_KEYS` is comma-separated.
- SQLite state defaults to `data/app.db` via `SQLITE_DB_PATH`. It stores daily source execution limits, per-target/per-key publish counts, and daily published-content hashes.

## Architecture overview

This is a Python 3.11+ Typer CLI that fetches crypto-related source data, normalizes it into content items, uses DeepAgents skills to generate Binance Square posts, and publishes them through Binance Square OpenAPI.

### Main layers

- `src/binance_square_bot/cli.py` defines the Typer command tree and delegates business logic to service classes under `services/cli/`.
- `services/source/` contains data-source adapters for ForesightNews, Followin, and Polymarket.
- `services/generation/` contains `TweetSourceItem`, source-to-item mappers, skill selection, tweet validation, and `DeepAgentTweetGenerator`.
- `agent_skills/` contains repository-local DeepAgents writing skills selected by `source_name` and `content_type`.
- `services/account_item_publisher.py` loops over each selected `TweetSourceItem` and each available Binance API key, generating account-specific copy immediately before publishing.
- `services/target/` contains publish-target adapters. `BinanceTarget` filters stop words, retries retryable publish failures, and masks API keys in logs.
- `services/cli/` contains workflow services that fetch data, map results into `TweetSourceItem` objects, return `items_fetched` and `items_generated`, and handle dry runs.
- `services/concurrent_executor.py` powers `binance-square-bot parallel`: run enabled source workflows concurrently, aggregate content items, apply item-level de-duplication and `total_per_run`, then delegate publishing to `AccountItemPublisher`.
- `services/storage.py` is the persistence boundary for execution limits, publish counters, and daily published-content hashes.

### Source families

- `FnSource` handles ForesightNews news, calendar events, airdrops, and fundraising.
- `FollowinSource` handles trending topics, IO-flow tokens, and discussion tokens.
- `PolymarketSource` fetches markets from Polymarket CLOB and supports research-style posts. It is disabled by default in the parallel workflow unless `--enable-polymarket` is passed.

### De-duplication and publishing behavior

- CLI services return normalized content items via `items_generated`; `items_fetched` reports fetched/considered item counts.
- Published-content identity is `source_name + content_type + identifier`.
- `SourceParallelPublisher` de-duplicates aggregated items by identity, filters items already published today, and passes remaining items to `AccountItemPublisher`.
- Each selected content item is generated once per available Binance API key. Full API keys must not be sent to DeepAgents; use masked keys or account ordinals in prompts/logs.
- Content is marked published only after at least one account publishes that item successfully. In dry-run mode, text is generated and printed with masked keys, but publish counters and content markers are not changed.

## GitHub Actions

- `.github/workflows/run-bot.yml` installs with Poetry, runs `poetry run binance-square-bot parallel --workers 10 --total-per-run 25`, then commits `data/app.db` back if it changed.
- `.github/workflows/test-bot.yml` is a manual dry-run workflow for running a selected CLI source with arguments.
