from pathlib import Path

import pytest

from binance_square_bot.services.generation import skills
from binance_square_bot.services.generation.models import TweetSourceItem
from binance_square_bot.services.generation.skills import select_skill_path, skills_root


def _item(source_name: str, content_type: str) -> TweetSourceItem:
    return TweetSourceItem(
        source_name=source_name,
        content_type=content_type,
        identifier=f"{source_name}:{content_type}",
        title="Title",
        summary="Summary",
    )


def test_skills_root_points_to_repository_agent_skills_directory():
    root = skills_root()
    expected_root = Path(skills.__file__).resolve().parents[4] / "agent_skills"

    assert root.name == "agent_skills"
    assert root.exists()
    assert root == expected_root


@pytest.mark.parametrize(
    ("source_name", "content_type", "expected_directory"),
    [
        ("FnSource", "news", "fn_news"),
        ("FnSource", "calendar", "fn_calendar"),
        ("FnSource", "airdrop", "fn_airdrop"),
        ("FnSource", "fundraising", "fn_fundraising"),
        ("FollowinSource", "topics", "followin_topics"),
        ("FollowinSource", "token", "followin_token"),
        ("FollowinSource", "io_flow", "followin_token"),
        ("FollowinSource", "discussion", "followin_token"),
        ("PolymarketSource", "polymarket_research", "polymarket_research"),
    ],
)
def test_select_skill_path_returns_expected_skill_directory(
    source_name: str,
    content_type: str,
    expected_directory: str,
):
    path = select_skill_path(_item(source_name, content_type))

    assert path.name == expected_directory
    assert path.parent == skills_root()
    assert (path / "SKILL.md").is_file()


def test_select_skill_path_rejects_unknown_mapping():
    item = _item("UnknownSource", "news")

    with pytest.raises(ValueError, match="No DeepAgents skill"):
        select_skill_path(item)


REQUIRED_SKILL_SECTIONS = [
    "## Role",
    "## Output contract",
    "## Source-specific objective",
    "## Recommended structures",
    "## Natural hook and market rhythm",
    "## Evidence and grounding rules",
    "## Account differentiation",
    "## Binance Square style rules",
    "## Forbidden patterns",
    "## Final self-check",
]

REQUIRED_SKILL_GUARDRAILS = [
    "Output only the final post body",
    "Do not use emojis",
    "Do not invent",
    "hashtag",
    "token tag",
    "account",
    "silently verify",
    "positive side",
    "cautious side",
    "specific watch point",
    "Do not tell readers to buy, sell, long, short",
    "not simply restate the headline",
]


@pytest.mark.parametrize(
    "skill_directory",
    [
        "fn_news",
        "fn_calendar",
        "fn_airdrop",
        "fn_fundraising",
        "followin_topics",
        "followin_token",
        "polymarket_research",
    ],
)
def test_skill_files_use_professional_instruction_structure(skill_directory: str):
    skill_file = skills_root() / skill_directory / "SKILL.md"
    content = skill_file.read_text(encoding="utf-8")

    for section in REQUIRED_SKILL_SECTIONS:
        assert section in content


@pytest.mark.parametrize(
    "skill_directory",
    [
        "fn_news",
        "fn_calendar",
        "fn_airdrop",
        "fn_fundraising",
        "followin_topics",
        "followin_token",
        "polymarket_research",
    ],
)
def test_skill_files_include_generation_guardrails(skill_directory: str):
    skill_file = skills_root() / skill_directory / "SKILL.md"
    content = skill_file.read_text(encoding="utf-8")

    for guardrail in REQUIRED_SKILL_GUARDRAILS:
        assert guardrail in content
