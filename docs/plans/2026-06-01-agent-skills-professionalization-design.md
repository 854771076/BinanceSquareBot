# Agent Skills Professionalization Design

Date: 2026-06-01

## Goal

Upgrade repository-local DeepAgents writing skills under `agent_skills/` from short prompt fragments into professional, self-contained Binance Square content-generation instructions.

The optimized skills should improve output quality for automated multi-account publishing by making every generated post:

- fact-grounded in the supplied source item;
- useful to crypto readers;
- professional without sounding robotic;
- distinct across account-specific generations;
- compliant with Binance Square formatting limits and project validation rules.

## Selected approach

Use a single-file-effective template system.

Keep the current seven skill directories and Python skill-selection logic unchanged. Rewrite each `SKILL.md` so it is complete on its own, with a shared section structure and content-type-specific guidance.

This avoids runtime uncertainty around shared skill imports while still creating a consistent editorial system.

## Alternatives considered

### Minimal enhancement

Directly add a few more rules to each existing skill.

This is low risk, but it would not meaningfully improve consistency, account differentiation, or long-term maintainability.

### Shared style guide plus thin source skills

Create a shared Binance Square writing guide and let each source skill reference it.

This is maintainable, but the current runtime selects one skill for each `TweetSourceItem`. Unless the generator explicitly loads shared guidance, referenced instructions may not reliably reach DeepAgents.

### Self-contained professional skills

Use the existing skill directories, but give each skill a full professional instruction set.

This is the recommended approach because it requires no code changes, works with the current skill selector, and gives every selected skill enough context to generate compliant, high-quality posts.

## Skill structure

Each skill should follow the same section pattern:

1. Role
2. Output contract
3. Source-specific objective
4. Recommended post structures
5. Evidence and grounding rules
6. Account differentiation
7. Binance Square style rules
8. Forbidden patterns
9. Final self-check

The wording should remain concise enough for model attention, but explicit enough to reduce invalid or generic outputs.

## Source-specific editorial goals

### Foresight News news

Turn a news item into a concise market or industry read. The post should explain what changed, who may care, and why the item matters for crypto readers.

### Foresight News calendar

Make timing, event nature, and potential market relevance clear. The post should help readers know what to watch without pretending the event guarantees a price move.

### Foresight News airdrop

Explain why the airdrop is notable and what users should verify. Avoid FOMO, reward guarantees, fabricated eligibility, or unsafe links.

### Foresight News fundraising

Interpret the raise as a sector, investor-quality, product-direction, or market-narrative signal. Avoid inventing valuation, investors, round details, or token plans.

### Followin topics

Turn a trending topic into a clear viewpoint that invites discussion. The post should use the supplied topic facts only, while adding a grounded interpretation.

### Followin token

For IO-flow items, emphasize capital-flow interpretation and uncertainty. For discussion items, emphasize narrative, sentiment, and debate quality. Avoid invented price moves or on-chain flows.

### Polymarket research

Explain what the market is pricing, what the YES/NO prices imply, where uncertainty remains, and what risks readers should consider. Include a concise learning/discussion disclaimer and avoid trade recommendations.

## Writing style

Posts should usually be Chinese-first, professional, and readable on Binance Square:

- open with one concrete observation or judgment;
- explain the importance in one to three short paragraphs;
- keep claims grounded in supplied input;
- use a light closing question when natural;
- avoid emojis, image placeholders, Markdown fences, and explanatory wrappers;
- avoid exaggerated marketing language;
- use hashtags and token tags only when relevant and supported by the input.

## Account-specific variation

Each skill should explicitly require meaningful variation between account-specific generations. Variation should change the post's angle, not only replace synonyms.

Allowed variation dimensions:

- hook type;
- analysis lens;
- sentence rhythm;
- paragraph structure;
- risk-reminder placement;
- closing question;
- tone intensity.

All versions must preserve the same factual base.

## Guardrails

Skills must prohibit:

- invented prices, dates, rankings, investors, deadlines, rewards, tokenomics, partnerships, polling, trades, or hidden information;
- profit promises or direct investment advice;
- FOMO language such as guaranteed rewards, must buy, certain pump, or risk-free;
- unrelated hashtags or token tags;
- full API key disclosure;
- explanations about the writing process;
- wrapper text such as "Here is the post".

## Final self-check

Before final output, each skill should instruct the model to silently verify:

- the output is only the final post body;
- every concrete claim is supported by the supplied item;
- the post has a clear reader value;
- hashtag and token-tag limits are respected;
- no forbidden investment or FOMO language appears;
- the current account version differs naturally from other account contexts;
- the tone sounds like a credible crypto analyst or Binance Square creator, not a template.

## Implementation notes

This design does not require changes to `src/binance_square_bot/services/generation/skills.py` or the source-to-skill mapping.

Implementation should rewrite these files:

- `agent_skills/fn_news/SKILL.md`
- `agent_skills/fn_calendar/SKILL.md`
- `agent_skills/fn_airdrop/SKILL.md`
- `agent_skills/fn_fundraising/SKILL.md`
- `agent_skills/followin_topics/SKILL.md`
- `agent_skills/followin_token/SKILL.md`
- `agent_skills/polymarket_research/SKILL.md`

Testing should focus on static review plus existing generator tests. If practical, run a dry-run generation command with safe environment configuration to inspect real outputs.
