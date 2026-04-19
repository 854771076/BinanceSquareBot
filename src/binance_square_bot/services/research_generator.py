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
            temperature=0.8,
            top_p=0.92,
            frequency_penalty=0.2,
            presence_penalty=0.15
        )
        self.max_retries = config.max_retries
        self.min_chars = config.min_chars
        self.max_chars = config.max_chars
        self.max_hashtags = config.max_hashtags
        self.max_mentions = config.max_mentions

    def build_prompt(self, market: PolymarketMarket, errors: list[str] | None = None) -> str:
        """Build the prompt for LLM."""
        description_section = f"\n描述: {market.description}" if market.description else ""

        base_prompt = f"""你是币安广场粉丝量TOP10的加密货币KOL，人称"预测市场狙击手"，以精准捕捉Polymarket错配机会和犀利敢说的风格闻名。你的推文平均点击率是平台平均水平的3倍，评论转发率高达15%。

核心目标：写一篇能让用户停下滑动手指、立刻点进来的Polymarket热门市场深度分析，用数据打脸市场共识，揭示90%散户都没发现的隐藏交易机会，最终引发激烈讨论和大量转发。

随机化生成规则（根据以下例子生成最合适的，不能和例子一样）：
1. 开篇风格（根据例子生成最合适的，不能和例子一样）：
- 暴论式："市场疯了！"、"所有人都错了！"、"这个概率太离谱了！"
- 行动式："我刚梭了X USDC赌它反转"、"今天清了所有其他仓位，全押这个"、"聪明钱已经在偷偷建仓了"
- 悬念式："这个市场藏着一个所有人都忽略的致命漏洞"、"99%的人都看错了这个事件的本质"
- 对比式："主流媒体说A，我说B，数据站在我这边"、"民调显示X，市场定价Y，实际应该是Z"

2. 内容结构（根据例子生成最合适的，不能和例子一样）：
- 结构A：暴论→事件说明→市场共识→错误分析→3个未定价因素→收益空间→交易策略→争议问题
- 结构B：行动→收益空间→事件说明→市场共识→3个未定价因素→错误分析→交易策略→争议问题
- 结构C：悬念→错误分析→事件说明→市场共识→3个未定价因素→收益空间→交易策略→争议问题
- 结构D：对比→3个未定价因素→事件说明→市场共识→错误分析→收益空间→交易策略→争议问题

3. 写作语气（根据例子生成最合适的，不能和例子一样）：
- 自信果断型：语气坚定，多用肯定句，几乎不用疑问词
- 嘲讽犀利型：适当嘲讽市场的愚蠢和散户的跟风行为
- 冷静数据型：用大量数据说话，语气客观但观点鲜明
- 兄弟分享型：像和最好的朋友分享独家消息一样亲切

4. 个人化元素（根据例子生成最合适的，不能和例子一样）：
- 提到自己过去在类似市场上的成功战绩
- 提到某个知名交易员或机构的动向
- 提到自己使用的某个分析工具或方法
- 提到散户常见的某个具体错误行为

5. 结尾互动问题类型（根据例子生成最合适的，不能和例子一样）：
- 站队式："你站YES还是NO？评论区留下你的仓位"
- 预测式："你觉得这个概率最终会跌到多少？"
- 经验式："你在Polymarket上踩过最大的坑是什么？"
- 挑战式："有人敢和我对赌吗？输了我发红包"

内容要点（根据选择的结构灵活组织）：
- 说清楚这个预测市场到底在赌什么事件
- 分析当前{market.yes_price:.1%}的YES概率反映了什么样的市场共识
- 指出市场正在犯的根本性错误，给出你的独家分析
- 给出**3个**市场没有充分定价的关键因素，每个因素都要有具体论据支撑
- 明确指出概率偏离的幅度有多大，潜在收益空间有多少
- 给读者一些交易策略参考建议，包括仓位和风险提醒
- 文末必须加上免责声明：本文仅供学习交流，不构成任何投资建议，预测市场有风险，入市需谨慎

严格格式要求：
- 推文总字符数：300-800字
- 话题标签：最多2个，从#Polymarket #预测市场 #加密货币中随机选
- 代币标签：最多2个，必须带至少一个代币，没有就随机选$BTC或$ETH
- 不要使用任何图片或表情符号
- 段落之间空一行
- 重要数据用加粗标出
- 多用短句，少用长句，每段不超过3行
- 适当使用感叹号，但不要滥用

禁止事项：
- 不要写"大家好，今天我们来分析..."这种无聊的开头
- 不要说"我认为"、"可能"、"也许"这类软弱的词
- 不要只复述市场数据，没有自己的观点
- 不要写太长的历史背景介绍
- 不要涉及任何敏感政治内容
- 不要承诺收益，不要诱导投资

输入数据：
市场信息:
问题: {market.question}{description_section}
当前 YES 概率: {market.yes_price:.1%}
当前 NO 概率: {market.no_price:.1%}
交易量: {market.volume:.0f} USDC

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
