"""
@file research_generator.py
@description AI 投资研报推文生成，使用 LLM 分析 Polymarket 市场并生成符合币安广场格式的研报
"""
import logging
from typing import Tuple, Optional, List

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from binance_square_bot.models.polymarket_market import PolymarketMarket
from binance_square_bot.models.tweet import Tweet
from binance_square_bot.config import config
from datetime import datetime

logger = logging.getLogger(__name__)


def format_validation(
    content: str,
    min_chars: int,
    max_chars: int,
    max_hashtags: int,
    max_mentions: int,
) -> None:
    """Validate generated content format constraints.
    Raises ValueError if validation fails.
    """
    errors: List[str] = []

    # Check character count
    length = len(content)
    if length < min_chars:
        errors.append(f"字符数 {length} 小于最小要求 {min_chars}")
    if length > max_chars:
        errors.append(f"字符数 {length} 大于最大要求 {max_chars}")

    # Check hashtag count
    hashtag_count = content.count("#")
    if hashtag_count > max_hashtags:
        errors.append(f"话题标签 #{hashtag_count} 个超过最大限制 {max_hashtags}")

    # Check mention count (token labels starting with $)
    mention_count = content.count("$")
    if mention_count > max_mentions:
        errors.append(f"代币标签 ${mention_count} 个超过最大限制 {max_mentions}")

    if errors:
        raise ValueError(", ".join(errors))


def retry_on_failure(func):
    """Retry decorator for generation methods."""
    def wrapper(*args, **kwargs):
        self = args[0]
        for attempt in range(self.max_retries):
            try:
                return func(*args, **kwargs)
            except ValueError as e:
                logger.warning(f"Generation attempt {attempt + 1} failed: {e}")
                if attempt == self.max_retries - 1:
                    raise
        raise ValueError("All retries exhausted")
    return wrapper


class ResearchGenerator:
    """AI generates Polymarket investment research tweets."""

    def __init__(self):
        self.llm = ChatOpenAI(
            api_key=SecretStr(config.llm_api_key),
            base_url=config.llm_base_url,
            model=config.llm_model,
            temperature=0.7,
        )
        self.max_retries = config.max_retries
        self.min_chars = config.min_chars
        self.max_chars = config.max_chars
        self.max_hashtags = config.max_hashtags
        self.max_mentions = config.max_mentions

    def build_prompt(self, market: PolymarketMarket, errors: Optional[List[str]] = None) -> str:
        """Build the prompt for LLM."""
        description_section = f"\n描述: {market.description}" if market.description else ""

        base_prompt = f"""你是一位资深的加密货币KOL，专注于预测市场（Polymarket）投资分析。你需要分析当前一个热门预测市场，生成适合币安广场用户的投资研报。

市场信息:
问题: {market.question}{description_section}
当前 YES 概率: {market.yes_price:.1%}
当前 NO 概率: {market.no_price:.1%}
交易量: {market.volume:.0f} USDC

写作要求:
- 专业但不晦涩，语言流畅自然
- 清晰描述事件是什么，当前市场概率反映了什么市场预期
- 分析概率是否存在偏离，是否存在潜在交易机会
- 观点要有洞察力，让读者觉得有价值
- 结尾可以引导讨论
- 保持独立客观，本文仅供学习交流，不构成投资建议
- 如果你认为这个问题涉及敏感内容，请直接说明无法分析

严格遵守格式要求:
1. 推文总字符数必须大于 {self.min_chars} 且小于 {self.max_chars}。
2. 话题标签（#开头）最多允许 {self.max_hashtags} 个。
3. 代币标签（$开头）最多允许 {self.max_mentions} 个。
4. 请直接输出推文内容，不要添加其他说明。
"""

        if errors:
            error_text = "\n".join(errors)
            base_prompt += f"""

上次生成不符合格式要求，请修正以下错误：
{error_text}
请重新生成。
"""

        return base_prompt

    def generate_research(self, market: PolymarketMarket, errors: Optional[List[str]] = None) -> Tweet:
        """Generate research tweet for the given market.
        Raises ValueError if generation fails after retries.
        """
        prompt = self.build_prompt(market, errors)
        response = self.llm.invoke([HumanMessage(content=prompt)])
        content = response.content.strip()

        # Validate format
        format_validation(
            content,
            min_chars=self.min_chars,
            max_chars=self.max_chars,
            max_hashtags=self.max_hashtags,
            max_mentions=self.max_mentions,
        )

        return Tweet(
            content=content,
            article_url="",
            generated_at=datetime.now(),
            validation_passed=True,
            validation_errors=[],
        )

    def generate_with_retry(self, market: PolymarketMarket) -> Tuple[Optional[Tweet], str]:
        """Generate with retry logic, returns (result, error_message)."""
        error = ""
        validation_errors: List[str] = []
        for attempt in range(self.max_retries):
            try:
                tweet = self.generate_research(market, validation_errors if validation_errors else None)
                return tweet, ""
            except ValueError as e:
                logger.warning(f"Generation attempt {attempt + 1} failed: {e}")
                error = str(e)
                validation_errors.append(error)

        logger.error(f"All {self.max_retries} generation attempts failed")
        return None, error