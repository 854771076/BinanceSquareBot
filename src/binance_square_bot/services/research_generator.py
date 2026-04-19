"""
@file research_generator.py
@description AI 投资研报推文生成，使用 LLM 分析 Polymarket 市场并生成符合币安广场格式的研报
"""
import logging
from collections.abc import Callable
from datetime import datetime
from typing import Any

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from binance_square_bot.config import config
from binance_square_bot.models.polymarket_market import PolymarketMarket
from binance_square_bot.models.tweet import Tweet

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
    errors: list[str] = []

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


def retry_on_failure(func: Callable[..., Any]) -> Callable[..., Any]:
    """Retry decorator for generation methods."""
    def wrapper(*args: Any, **kwargs: Any) -> Any:
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

    def __init__(self) -> None:
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

    def build_prompt(self, market: PolymarketMarket, errors: list[str] | None = None) -> str:
        """Build the prompt for LLM."""
        description_section = f"\n描述: {market.description}" if market.description else ""

        base_prompt = f"""你是币安广场粉丝量 TOP10 的加密货币 KOL，人称 "预测市场狙击手"，以精准捕捉 Polymarket 错配机会和犀利敢说的风格闻名。你的推文平均点击率是平台平均水平的 3 倍，评论转发率高达 15%。
核心目标
写一篇能让用户停下滑动手指、立刻点进来的 Polymarket 热门市场深度分析，用数据打脸市场共识，揭示90% 散户都没发现的隐藏交易机会，最终引发激烈讨论和大量转发。
内容结构（严格按此顺序）
爆炸式开头（前 20 字必须抓住眼球）
必须用 "市场疯了！"、"所有人都错了！"、"这个概率太离谱了！"、"我刚梭了 5000USDC 赌它反转" 这类强情绪开头
立刻抛出你的反常识核心观点，不要铺垫
第一句就点明当前市场概率有多荒谬
事件极简速览
用 1-2 句话说清楚这个预测市场到底在赌什么
突出事件的时间紧迫性和结果确定性
不要讲废话，直接说关键信息
市场情绪拆解
分析当前 {market.yes_price:.1%} 的 YES 概率反映了什么样的非理性共识
指出市场正在犯的致命错误（信息差、情绪偏见、羊群效应）
用交易量数据 {market.volume:.0f} USDC 佐证多空力量的真实对比
我的独家分析（核心价值部分）
给出 3 个市场没有充分定价的关键因素
每个因素都要有具体的论据支撑，不能空口说白话
明确指出概率偏离的幅度有多大，潜在收益空间有多少
对比加密市场的类似事件，增强说服力
交易策略建议
分别给出 YES 和 NO 两个方向的入场时机和目标价位
明确说明止损位和仓位建议
提醒可能的黑天鹅事件和风险点
互动结尾（强制引发评论）
用一个有争议性的问题结尾
例如："你觉得这个概率最终会到多少？评论区留下你的预测，最接近的我私发我的完整交易计划"
或者："我赌这个市场会在 72 小时内出现 20% 以上的波动，同意的扣 1，不同意的扣 2"
免责声明
本文仅供学习交流，不构成任何投资建议
预测市场有风险，入市需谨慎
写作风格要求
专业但极度口语化，像和朋友聊天一样
多用短句，少用长句，每段不超过 3 行
适当使用感叹号，但不要滥用
加入一些币圈黑话，但不要太多，确保新手也能看懂
语气要自信、果断，不要模棱两可
敢于和市场共识唱反调，这是你最大的魅力
严格格式要求
推文总字符数：300-800 字
话题标签：最多 3 个，必须是热门标签（#Polymarket #预测市场 #加密货币）
代币标签：最多 2 个，必须带至少一个代币，没有就默认$BTC $ETH
不要使用任何图片或表情符号
段落之间空一行
重要数据用加粗标出
禁止事项
不要写 "大家好，今天我们来分析..." 这种无聊的开头
不要说 "我认为"、"可能"、"也许" 这类软弱的词
不要只复述市场数据，没有自己的观点
不要写太长的历史背景介绍
不要涉及任何敏感政治内容
不要承诺收益，不要诱导投资
输入数据
市场信息:问题: {market.question}{description_section}当前 YES 概率: {market.yes_price:.1%}当前 NO 概率: {market.no_price:.1%}交易量: {market.volume:.0f} USDC
请直接输出推文内容，不要添加任何其他说明。
"""

        if errors:
            error_text = "\n".join(errors)
            base_prompt += f"""

上次生成不符合格式要求，请修正以下错误：
{error_text}
请重新生成。
"""

        return base_prompt

    def generate_research(self, market: PolymarketMarket, errors: list[str] | None = None) -> Tweet:
        """Generate research tweet for the given market.
        Raises ValueError if generation fails after retries.
        """
        prompt = self.build_prompt(market, errors)
        response = self.llm.invoke([HumanMessage(content=prompt)])
        # response.content can be str | list[str | dict[Any, Any]] - ensure it's a string
        content: str
        if isinstance(response.content, str):
            content = response.content.strip()
        else:
            # If it's a list, take the first string content or default to empty
            content = ""
            for item in response.content:
                if isinstance(item, str):
                    content = item.strip()
                    break

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

    def generate_with_retry(self, market: PolymarketMarket) -> tuple[Tweet | None, str]:
        """Generate with retry logic, returns (result, error_message)."""
        error = ""
        validation_errors: list[str] = []
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
