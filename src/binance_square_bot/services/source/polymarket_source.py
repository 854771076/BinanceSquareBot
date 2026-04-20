from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, SecretStr
import httpx
from loguru import logger
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

from binance_square_bot.services.base import BaseSource
from binance_square_bot.config import config


class PolymarketMarket(BaseModel):
    """Polymarket market model."""
    condition_id: str
    question: str
    yes_price: float
    no_price: float
    volume: float
    image: Optional[str] = None
    description: Optional[str] = None


class PolymarketSource(BaseSource):
    """Polymarket data source - fetches markets and generates AI research tweets."""

    Model = PolymarketMarket

    class Config(BaseSource.Config):
        enabled: bool = False
        host: str = "https://clob.polymarket.com"
        min_volume_threshold: float = 1000.0
        min_win_rate: float = 0.6
        max_win_rate: float = 0.95
        daily_max_executions: int = 10

    def __init__(self):
        super().__init__()
        self.client = httpx.Client(timeout=30.0)
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
        self.max_mentions = 2

    def _validate_format(self, content: str) -> None:
        """Validate generated content format constraints.
        Raises ValueError if validation fails.
        """
        errors: List[str] = []
        length = len(content)
        if length < self.min_chars:
            errors.append(f"字符数 {length} 小于最小要求 {self.min_chars}")
        if length > self.max_chars:
            errors.append(f"字符数 {length} 大于最大要求 {self.max_chars}")

        hashtag_count = content.count("#")
        if hashtag_count > self.max_hashtags:
            errors.append(f"话题标签 #{hashtag_count} 个超过最大限制 {self.max_hashtags}")

        mention_count = content.count("$")
        if mention_count > self.max_mentions:
            errors.append(f"代币标签 ${mention_count} 个超过最大限制 {self.max_mentions}")

        if errors:
            raise ValueError(", ".join(errors))

    def _build_prompt(self, market: PolymarketMarket, errors: Optional[List[str]] = None) -> str:
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

内容要点（根据选择的结构灵活组织）：
- 说清楚这个预测市场到底在赌什么事件
- 分析当前{market.yes_price:.1%}的YES概率反映了什么样的市场共识
- 指出市场正在犯的根本性错误，给出你的独家分析
- 给出3个市场没有充分定价的关键因素，每个因素都要有具体论据支撑
- 明确指出概率偏离的幅度有多大，潜在收益空间有多少
- 给读者一些交易策略参考建议，包括仓位和风险提醒
- 文末必须加上免责声明：本文仅供学习交流，不构成任何投资建议，预测市场有风险，入市需谨慎

严格格式要求：
- 推文总字符数：300-800字
- 话题标签：最多2个，从#Polymarket #预测市场 #加密货币中随机选
- 代币标签：最多2个，必须带至少一个代币，没有就随机选$BTC或$ETH
- 不要使用任何图片或表情符号
- 段落之间空一行
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

    def fetch(self) -> List[PolymarketMarket]:
        """Fetch all markets from Polymarket."""
        url = f"{self.config.host}/markets"

        try:
            response = self.client.get(url)
            response.raise_for_status()
            data = response.json()

            markets: List[PolymarketMarket] = []

            # Handle different response formats - could be list or dict with data key
            if isinstance(data, list):
                market_list = data
            elif isinstance(data, dict) and "data" in data:
                market_list = data["data"]
            else:
                market_list = []

            for item in market_list:
                try:
                    # Get outcome prices
                    outcomes = item.get("outcomes", [])
                    outcome_prices = item.get("outcomePrices", [])

                    yes_price = 0.0
                    no_price = 0.0

                    for i, outcome in enumerate(outcomes):
                        if outcome.lower() == "yes" and i < len(outcome_prices):
                            yes_price = float(outcome_prices[i])
                        elif outcome.lower() == "no" and i < len(outcome_prices):
                            no_price = float(outcome_prices[i])

                    market = PolymarketMarket(
                        condition_id=item.get("conditionId", ""),
                        question=item.get("question", ""),
                        yes_price=yes_price,
                        no_price=no_price,
                        volume=float(item.get("volume", 0)),
                        image=item.get("image"),
                        description=item.get("description"),
                    )
                    markets.append(market)
                except Exception as e:
                    logger.warning(f"Failed to parse market: {e}")
                    continue

            logger.info(f"Fetched {len(markets)} markets from Polymarket")
            return markets

        except Exception as e:
            logger.error(f"Failed to fetch markets: {e}")
            return []

    def generate(self, markets: List[PolymarketMarket]) -> List[str]:
        """Generate AI research tweets from high-confidence markets."""
        # Filter for high volume and extreme probability
        candidate_markets = [
            m for m in markets
            if m.volume >= self.config.min_volume_threshold
            and (
                m.yes_price >= self.config.min_win_rate
                or m.no_price >= self.config.min_win_rate
            )
            and (
                m.yes_price <= self.config.max_win_rate
                or m.no_price <= self.config.max_win_rate
            )
        ]

        # Sort by volume descending
        candidate_markets.sort(key=lambda m: m.volume, reverse=True)

        tweets = []
        for market in candidate_markets[:5]:  # Top 5 by volume
            try:
                tweet = self._generate_single_tweet(market)
                if tweet:
                    tweets.append(tweet)
            except Exception as e:
                logger.error(f"Failed to generate tweet for market '{market.question}': {e}")
                continue

        logger.info(f"Generated {len(tweets)} research tweets from markets")
        return tweets

    def _generate_single_tweet(self, market: PolymarketMarket) -> Optional[str]:
        """Generate a single research tweet with retry."""
        validation_errors: List[str] = []
        for attempt in range(self.max_retries):
            try:
                prompt = self._build_prompt(market, validation_errors if validation_errors else None)
                response = self.llm.invoke([HumanMessage(content=prompt)])

                # Handle response content - could be str or list
                if isinstance(response.content, str):
                    content = response.content.strip()
                else:
                    content = ""
                    for item in response.content:
                        if isinstance(item, str):
                            content = item.strip()
                            break

                # Validate format
                self._validate_format(content)
                return content

            except ValueError as e:
                logger.warning(f"Generation attempt {attempt + 1} failed: {e}")
                validation_errors.append(str(e))

        logger.error(f"All {self.max_retries} generation attempts failed for market")
        return None
