from pathlib import Path

from binance_square_bot.services.generation.models import TweetSourceItem

_SKILL_BY_SOURCE_AND_TYPE = {
    ("FnSource", "news"): "fn_news",
    ("FnSource", "calendar"): "fn_calendar",
    ("FnSource", "airdrop"): "fn_airdrop",
    ("FnSource", "fundraising"): "fn_fundraising",
    ("FollowinSource", "topics"): "followin_topics",
    ("FollowinSource", "token"): "followin_token",
    ("FollowinSource", "io_flow"): "followin_token",
    ("FollowinSource", "discussion"): "followin_token",
    ("PolymarketSource", "polymarket_research"): "polymarket_research",
}


def skills_root() -> Path:
    """Return the repository-local DeepAgents skills directory."""
    return Path(__file__).resolve().parents[4] / "agent_skills"


def select_skill_path(item: TweetSourceItem) -> Path:
    """Select the DeepAgents skill directory for a normalized source item."""
    key = (item.source_name, item.content_type)
    skill_directory = _SKILL_BY_SOURCE_AND_TYPE.get(key)
    if skill_directory is None:
        raise ValueError(
            "No DeepAgents skill for "
            f"source_name={item.source_name!r}, content_type={item.content_type!r}"
        )
    return skills_root() / skill_directory

def get_humanizer_skill_path() -> Path:
    """Return the DeepAgents skill directory for humanizer."""
    return skills_root() / "humanizer"