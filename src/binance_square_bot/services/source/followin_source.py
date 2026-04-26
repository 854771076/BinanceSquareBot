import json
import time
from datetime import datetime
from typing import List, Optional
from html.parser import HTMLParser
from curl_cffi import requests
from pydantic import BaseModel, SecretStr
from loguru import logger
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

from binance_square_bot.services.base import BaseSource
from binance_square_bot.config import config


class FollowinTopic(BaseModel):
    """Followin trending topic model."""
    id: int
    title: str
    summary: str
    url: str


class FollowinToken(BaseModel):
    """Followin token model for IO flow and discussion."""
    id: int
    name: str
    symbol: str
    summary: str
    token_quote: Optional[dict] = None
    category: str  # "io_flow" or "discussion"


class FollowinSource(BaseSource):
    """Followin data source - fetches trending topics, IO flow tokens and discussion tokens."""

    Model = FollowinTopic

    class Config(BaseSource.Config):
        enabled: bool = True
        base_url: str = "https://api.followin.io"
        web_base_url: str = "https://followin.io"
        timeout: int = 30
        daily_max_executions: int = 30
        max_items_per_category: int = 2
        max_retries: int = 3  # 请求失败重试次数
        retry_delay: float = 2.0  # 重试间隔（秒）
        request_delay: float = 1.0  # 每个请求之间的间隔（秒）

    def __init__(self):
        super().__init__()
        self.session = requests.Session()
        self.session.headers.update({
            'accept': 'application/json, text/plain, */*',
            'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
            'cache-control': 'no-cache',
            'content-type': 'application/json',
            'origin': 'https://followin.io',
            'pragma': 'no-cache',
            'referer': 'https://followin.io/',
        })
        self.llm = ChatOpenAI(
            api_key=SecretStr(config.llm_api_key),
            base_url=config.llm_base_url,
            model=config.llm_model,
            temperature=0.8,
            top_p=0.92,
        )
        self.max_retries = config.max_retries
        self.min_chars = config.min_chars
        self.max_chars = config.max_chars
        self.max_hashtags = config.max_hashtags
        self.max_mentions = config.max_mentions

        self.processed_ids = set()
        self._last_request_time = 0.0

    def _request_with_retry(self, method: str, url: str, is_session: bool = True, **kwargs) -> requests.Response:
        """Make HTTP request with retry logic for rate limiting (429)."""
        for attempt in range(self.config.max_retries):
            # Rate limiting - delay between requests
            elapsed = time.time() - self._last_request_time
            if elapsed < self.config.request_delay:
                time.sleep(self.config.request_delay - elapsed)

            try:
                if is_session:
                    resp = self.session.request(method, url, **kwargs)
                else:
                    resp = requests.request(method, url, **kwargs)

                self._last_request_time = time.time()
                resp.raise_for_status()
                return resp

            except requests.errors.RequestsError as e:
                if e.response and e.response.status_code == 429:
                    # Rate limited - wait longer and retry
                    wait_time = self.config.retry_delay * (attempt + 1) * 2
                    logger.warning(f"Rate limited (429) for {url}, retrying in {wait_time}s (attempt {attempt + 1}/{self.config.max_retries})")
                    time.sleep(wait_time)
                    continue
                else:
                    # Other HTTP errors - retry with normal delay
                    if attempt < self.config.max_retries - 1:
                        wait_time = self.config.retry_delay * (attempt + 1)
                        logger.warning(f"HTTP error {e} for {url}, retrying in {wait_time}s (attempt {attempt + 1}/{self.config.max_retries})")
                        time.sleep(wait_time)
                        continue
                    raise

            except Exception as e:
                # Connection errors, timeouts - retry
                if attempt < self.config.max_retries - 1:
                    wait_time = self.config.retry_delay * (attempt + 1)
                    logger.warning(f"Request error {e} for {url}, retrying in {wait_time}s (attempt {attempt + 1}/{self.config.max_retries})")
                    time.sleep(wait_time)
                    continue
                raise

        # If all retries failed
        raise Exception(f"All {self.config.max_retries} retries failed for {url}")

    class NextDataParser(HTMLParser):
        """Parse NEXT_DATA from HTML page."""
        def __init__(self):
            super().__init__()
            self.next_data = None
            self.in_target_script = False

        def handle_starttag(self, tag, attrs):
            if tag == 'script':
                for name, value in attrs:
                    if name == 'id' and value == '__NEXT_DATA__':
                        self.in_target_script = True
                        break

        def handle_endtag(self, tag):
            if tag == 'script' and self.in_target_script:
                self.in_target_script = False

        def handle_data(self, data):
            if self.in_target_script:
                self.next_data = data

    def _fetch_trending_topics(self,page_size: int = 5) -> List[FollowinTopic]:
        """Fetch trending topics list and details."""
        url = f"{self.config.base_url}/trending_topic/ranks"
        try:
            resp = self._request_with_retry(
                'POST', url, is_session=True,
                impersonate='chrome', timeout=self.config.timeout, json={}
            )
            data = resp.json()

            if data.get('code') != 2000:
                logger.warning(f"Followin trending topics API error: {data}")
                return []

            topics = data.get('data', {}).get('list', [])[0].get('topics', [])[:page_size]
            result: List[FollowinTopic] = []

            for item in topics:
                topic_id = item.get('id')
                if topic_id in self.processed_ids:
                    continue

                title = item.get('name', '').strip()
                summary = self._fetch_topic_detail(topic_id)

                if summary:
                    result.append(FollowinTopic(
                        id=topic_id,
                        title=title,
                        summary=summary,
                        url=f"{self.config.web_base_url}/zh-Hans/trendingTopic/{topic_id}"
                    ))

            logger.info(f"Fetched {len(result)} trending topics from Followin")
            return result[:self.config.max_items_per_category]

        except Exception as e:
            logger.error(f"Failed to fetch trending topics: {e}")
            return []

    def _fetch_topic_detail(self, topic_id: int) -> str:
        """Fetch trending topic AI summary from web page."""
        url = f"{self.config.web_base_url}/zh-Hans/trendingTopic/{topic_id}"
        try:
            headers = {
                'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
                'cache-control': 'no-cache',
                'pragma': 'no-cache',
                'priority': 'u=0, i',
                'referer': 'https://followin.io/zh-Hans/trendingTopicList',
                'sec-ch-ua': '"Microsoft Edge";v="147", "Not.A/Brand";v="8", "Chromium";v="147"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"Windows"',
                'sec-fetch-dest': 'document',
                'sec-fetch-mode': 'navigate',
                'sec-fetch-site': 'same-origin',
                'sec-fetch-user': '?1',
                'upgrade-insecure-requests': '1',
                'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36 Edg/147.0.0.0',
                # 'cookie': 'TZ=8; G=jIPvKoLaE6yxNmfAaHnftppSotawKqSbtxMsvFIoaGx1msr0aG-_qRfneiOt3Ieh; _ga=GA1.1.1217072458.1776697862; _ga_RDXGD4Z1XV=GS2.1.s1776697862$o1$g1$t1776698019$j60$l0$h0',
            }
            resp = self._request_with_retry(
                'GET', url, is_session=False,
                impersonate='chrome', timeout=self.config.timeout, headers=headers
            )

            parser = self.NextDataParser()
            parser.feed(resp.text)
            next_data = parser.next_data

            if next_data:
                data = json.loads(next_data)
                queries = data.get('props', {}).get('pageProps', {}).get('dehydratedState', {}).get('queries', [])
                for query in queries:
                    state_data = query.get('state', {}).get('data', {})
                    if isinstance(state_data, dict) and 'deep_ai_summariy' in state_data:
                        return state_data['deep_ai_summariy'].get('summary', '')

            return ""
        except Exception as e:
            logger.warning(f"Failed to fetch topic detail {topic_id}: {e}")
            return ""

    def _fetch_io_flow_tokens(self,page_size: int = 5) -> List[FollowinToken]:
        """Fetch IO flow position change tokens."""
        url = f"{self.config.base_url}/tag/token/recommended"
        json_data = {'type': 'position_changes_1h', 'count': page_size}
        try:
            resp = self._request_with_retry(
                'POST', url, is_session=True,
                json=json_data, impersonate='chrome', timeout=self.config.timeout
            )
            data = resp.json()

            if data.get('code') != 2000:
                logger.warning(f"Followin IO flow API error: {data}")
                return []

            response_data = data.get('data', {})
            token_list = response_data.get('list', [])[:10]
            token_quotes = response_data.get('token_quotes', {})
            result: List[FollowinToken] = []

            for item in token_list:
                token_id = item.get('id')
                token_key = str(token_id)

                if token_id in self.processed_ids:
                    continue

                summary = self._fetch_token_discussion_summary(token_id)
                try:
                    token_quote = token_quotes.get(token_key, [None])[0] if token_key in token_quotes else None
                except:
                    continue

                if summary:
                    result.append(FollowinToken(
                        id=token_id,
                        name=item.get('name', ''),
                        symbol=item.get('symbol', ''),
                        summary=summary,
                        token_quote=token_quote,
                        category="io_flow"
                    ))

            logger.info(f"Fetched {len(result)} IO flow tokens from Followin")
            return result[:self.config.max_items_per_category]

        except Exception as e:
            logger.error(f"Failed to fetch IO flow tokens: {e}")
            return []

    def _fetch_discussion_tokens(self,page_size: int = 5) -> List[FollowinToken]:
        """Fetch most discussed tokens."""
        url = f"{self.config.base_url}/tag/token/recommended"
        json_data = {'type': 'discussion', 'count': page_size}
        try:
            resp = self._request_with_retry(
                'POST', url, is_session=True,
                json=json_data, impersonate='chrome', timeout=self.config.timeout
            )
            data = resp.json()

            if data.get('code') != 2000:
                logger.warning(f"Followin discussion tokens API error: {data}")
                return []

            response_data = data.get('data', {})
            token_list = response_data.get('list', [])[:10]
            token_quotes = response_data.get('token_quotes', {})
            result: List[FollowinToken] = []

            for item in token_list:
                token_id = item.get('id')
                token_key = str(token_id)

                if token_id in self.processed_ids:
                    continue

                summary = self._fetch_token_discussion_summary(token_id)
                token_quote = token_quotes.get(token_key, [None])[0] if token_key in token_quotes else None

                if summary:
                    result.append(FollowinToken(
                        id=token_id,
                        name=item.get('name', ''),
                        symbol=item.get('symbol', ''),
                        summary=summary,
                        token_quote=token_quote,
                        category="discussion"
                    ))

            logger.info(f"Fetched {len(result)} discussion tokens from Followin")
            return result[:self.config.max_items_per_category]

        except Exception as e:
            logger.error(f"Failed to fetch discussion tokens: {e}")
            return []

    def _fetch_token_discussion_summary(self, token_id: int) -> str:
        """Fetch token discussion summary from API."""
        url = f"{self.config.base_url}/tag/discussion/summary"
        json_data = {'id': token_id}
        try:
            resp = self._request_with_retry(
                'POST', url, is_session=True,
                json=json_data, impersonate='chrome', timeout=self.config.timeout
            )
            data = resp.json()

            if data.get('code') == 2000:
                return data.get('data', {}).get('summary', '')
            return ""
        except Exception as e:
            logger.warning(f"Failed to fetch token summary {token_id}: {e}")
            return ""

    def fetch(self) -> List:
        """Fetch all data from Followin (deprecated - use category-specific methods)."""
        return self.fetch_trending_topics() + self.fetch_io_flow_tokens() + self.fetch_discussion_tokens()

    def fetch_trending_topics(self) -> List[FollowinTopic]:
        """Fetch only trending topics."""
        self.processed_ids = set()
        topics = self._fetch_trending_topics()
        logger.info(f"Fetched {len(topics)} trending topics from Followin")
        return topics

    def fetch_io_flow_tokens(self) -> List[FollowinToken]:
        """Fetch only IO flow tokens."""
        self.processed_ids = set()
        tokens = self._fetch_io_flow_tokens()
        logger.info(f"Fetched {len(tokens)} IO flow tokens from Followin")
        return tokens

    def fetch_discussion_tokens(self) -> List[FollowinToken]:
        """Fetch only discussion tokens."""
        self.processed_ids = set()
        tokens = self._fetch_discussion_tokens()
        logger.info(f"Fetched {len(tokens)} discussion tokens from Followin")
        return tokens

    def _validate_format(self, content: str) -> None:
        """Validate generated content format constraints."""
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

    def _build_topic_prompt(self, topic: FollowinTopic, errors: Optional[List[str]] = None) -> str:
        """Build prompt for trending topic."""
        base_prompt = f"""你是币安广场的加密货币KOL，擅长把热点话题转化为引人点击的观点型推文。

核心目标：基于以下Followin热点话题和AI总结，写一篇有独立见解的推文，能引发评论讨论。

写作风格：
- 观点鲜明，立场明确
- 用口语化表达，像和朋友聊天一样
- 可以适当带点情绪
- 多用短句，段落清晰

内容结构：
1. 犀利开头：一句话点出话题的核心影响
2. 深度解读：这个话题为什么重要？市场会怎么反应？
3. 独家角度：给出别人没注意到的观察
4. 结尾互动：抛出问题引导读者评论

格式要求：
- 总字符数：100-800字
- 话题标签：最多{self.max_hashtags}个，#Web3 #加密货币 等贴合文章内容的标签
- 代币标签：最多{self.max_mentions}个，列出新闻内容提及的代币，没有就用$BTC $ETH
- 不要使用表情符号
- 段落之间空一行

输入话题：
标题: {topic.title}
AI总结: {topic.summary}

请直接输出推文内容，不要添加任何其他说明。
"""
        if errors:
            error_text = "\n".join(errors)
            base_prompt += f"""

上次生成不符合格式要求，请修正以下错误：
{error_text}
请重新生成。
"""
        # logger.info(f"Prompt: {base_prompt}")
        return base_prompt

    def _build_token_prompt(self, token: FollowinToken, errors: Optional[List[str]] = None) -> str:
        """Build prompt for token discussion."""
        category_name = "资金异动" if token.category == "io_flow" else "讨论热度"

        price_info = ""
        if token.token_quote and isinstance(token.token_quote, dict):
            price_info =  token.token_quote

        base_prompt = f"""你是币安广场的加密货币KOL，人称"链上侦探"，擅长把{category_name}币种转化为犀利的市场分析推文。

核心目标：基于以下币种的讨论摘要，写一篇有深度、有观点的分析推文，能引发激烈讨论。

写作风格：
- 自信果断，多用肯定句
- 适当带点嘲讽或惊讶的情绪
- 用口语化表达，像和兄弟分享消息一样
- 多用短句，段落清晰

内容结构：
1. 劲爆开头：一句话点出这个币种正在发生什么
2. 现象解读：为什么这个币种突然出现{category_name}变化？
3. 深度分析：这个变化背后可能意味着什么？
4. 独家观察：给出你对这个币种的独特看法
5. 结尾互动：抛出问题引导读者评论

格式要求：
- 总字符数：100-800字
- 话题标签：最多{self.max_hashtags}个，#Web3 #加密货币 #{token.symbol} 等贴合文章内容的标签
- 代币标签：最多{self.max_mentions}个，${token.symbol} 等,从新闻内容中提取, 没有就用$BTC $ETH
- 不要使用表情符号
- 段落之间空一行

输入数据：
币种: {token.name} (${token.symbol})
类型: {category_name}
讨论摘要: {token.summary}
价格数据：{price_info}

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

    def generate(self, items: List) -> List[str]:
        """Generate AI tweet content from all items."""
        tweets = []

        for item in items:
            try:
                if isinstance(item, FollowinTopic):
                    tweet = self._generate_single_tweet(item, self._build_topic_prompt)
                elif isinstance(item, FollowinToken):
                    tweet = self._generate_single_tweet(item, self._build_token_prompt)
                else:
                    continue

                if tweet:
                    tweets.append(tweet)
            except Exception as e:
                logger.error(f"Failed to generate tweet for item: {e}")
                continue

        logger.info(f"Generated {len(tweets)} tweets from Followin items")
        return tweets

    def _generate_single_tweet(self, item, prompt_builder) -> Optional[str]:
        """Generate a single tweet with retry."""
        validation_errors: List[str] = []
        for attempt in range(self.max_retries):
            try:
                prompt = prompt_builder(item, validation_errors if validation_errors else None)
                response = self.llm.invoke([HumanMessage(content=prompt)])

                if isinstance(response.content, str):
                    content = response.content.strip()
                else:
                    content = ""
                    for part in response.content:
                        if isinstance(part, str):
                            content = part.strip()
                            break

                self._validate_format(content)

                return content

            except ValueError as e:
                logger.warning(f"Generation attempt {attempt + 1} failed: {e}")
                validation_errors.append(str(e))

        logger.error(f"All {self.max_retries} generation attempts failed")
        return None
