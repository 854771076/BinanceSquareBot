# Uniform Skill Hooks Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a consistent natural hook and light market-rhythm rule to every DeepAgents writing skill without changing generation code.

**Architecture:** Update only repository-local `agent_skills/*/SKILL.md` files and their structure tests. Each skill receives the same `## Natural hook and market rhythm` section between `Recommended structures` and `Evidence and grounding rules`, preserving existing source-specific objectives and guardrails.

**Tech Stack:** Markdown prompt files, pytest.

---

### Task 1: Add failing tests for uniform hook/rhythm rules

**Files:**
- Modify: `tests/services/generation/test_skills.py`

**Step 1: Write the failing test**

Add `"## Natural hook and market rhythm"` to `REQUIRED_SKILL_SECTIONS` after `"## Recommended structures"`.

Add required guardrail phrases to `REQUIRED_SKILL_GUARDRAILS`:

```python
"positive side",
"cautious side",
"specific watch point",
"Do not tell readers to buy, sell, long, short",
"not simply restate the headline",
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/services/generation/test_skills.py -v`

Expected: FAIL because none or not all skill files contain the new section and required phrases.

---

### Task 2: Add uniform section to all skill files

**Files:**
- Modify: `agent_skills/fn_news/SKILL.md`
- Modify: `agent_skills/fn_calendar/SKILL.md`
- Modify: `agent_skills/fn_airdrop/SKILL.md`
- Modify: `agent_skills/fn_fundraising/SKILL.md`
- Modify: `agent_skills/followin_topics/SKILL.md`
- Modify: `agent_skills/followin_token/SKILL.md`
- Modify: `agent_skills/polymarket_research/SKILL.md`

**Step 1: Insert the same section**

Insert this section after each file's `## Recommended structures` bullet list and before `## Evidence and grounding rules`:

```markdown
## Natural hook and market rhythm

- Open with a concrete hook: a market signal, tension, contradiction, or watch variable. Do not simply restate the headline.
- Add light long/short rhythm without giving trading advice:
  - positive side: what supports attention, momentum, funding, adoption, liquidity, or narrative strength;
  - cautious side: what remains unproven, overheated, illiquid, uncertain, or dependent on follow-up data.
- Use neutral phrasing such as 积极的一面是, 谨慎看, 多头需要证明, or 风险在于.
- Do not tell readers to buy, sell, long, short, chase, or avoid.
- End with a specific watch point or tension. Avoid generic endings like 你怎么看？
- Make readers want to follow the next variable, not rush into a trade.
```

**Step 2: Run skill tests**

Run: `pytest tests/services/generation/test_skills.py -v`

Expected: PASS.

---

### Task 3: Run regression verification

**Files:**
- Test only.

**Step 1: Run generation-related tests**

Run: `pytest tests/services/generation/ -v`

Expected: PASS.

**Step 2: Run full suite**

Run: `pytest tests/ -v`

Expected: PASS.
