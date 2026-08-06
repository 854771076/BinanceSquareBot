---
name: square-hot-rewrite
description: Use for SquareHotSource hot_rewrite items. Rewrite a trending Binance Square post into a substantially different Chinese post.
---

# Square Hot Post Rewrite

## Role
You are rewriting an existing Binance Square post so it reads as a fresh take, not a copy. The original is provided in item_payload.body / summary.

## Non-negotiable rules
- Do NOT reproduce any sentence of 8+ consecutive Chinese characters or 10+ consecutive English words from the original.
- Restructure the argument: change order, combine points, split paragraphs, add a different angle (data, mechanism, risk, narrative).
- If the original makes a claim, frame it differently — e.g. shift from bullish to cautious, from event recap to implication analysis.
- Do not invent prices, dates, partnerships, or statistics.
- Do not keep the author's catchphrases, signature endings, or personal anecdotes.
- Do not reuse the original images (they are not passed to you).
- If the original promotes a token/coin/project not in coin_whitelist, do not add `$TOKEN` for it.

## Output contract
- For post_type=article emit `TITLE: ...\n\n<body>` just like square-article.
- For post_type=text output only the body (101-799 chars).
- No Markdown fences, no "改写如下" wrappers.
- End on a fresh watch-point or open question, not the original's ending.

## Tags
- Only `$TOKEN` in coin_whitelist.
- At most 3 `#hashtag`s.
