"""
@file generator.py
@description LangGraph推文生成工作流，包含格式校验和自动重试
@design-doc docs/06-ai-design/agent-flow/tweet-generation-flow.md
@task-id BE-08
@created-by fullstack-dev-workflow
"""

from typing import TypedDict, List, Optional
from datetime import datetime

from langchain.chat_models import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langgraph.graph import StateGraph, END

from ..models.article import Article
from ..models.tweet import Tweet
from ..config import config


class GraphState(TypedDict):
    """推文生成工作流状态"""
    article: Article
    prompt: str
    generated_text: str
    validation_errors: List[str]
    retry_count: int
    max_retries: int
    is_valid: bool


def _get_system_prompt(errors: Optional[List[str]] = None) -> str:
    """获取系统Prompt"""
    base_prompt = """你是一位专业的加密货币内容创作者，需要将一篇来自Fn的新闻改写成吸引币安广场用户的推文。

严格遵守以下格式要求：

1. 推文总字符数必须大于 100 且小于 800。
2. 话题标签（#开头）最多允许 2 个。
3. 代币标签（$开头）最多允许 2 个。
4. 内容必须符合新闻事实，不能编造信息。
5. 内容需要吸引观众，最后可以引导关注或讨论。

请直接输出推文内容，不要添加其他说明。
"""

    if errors and len(errors) > 0:
        error_text = "\n".join(f"- {error}" for error in errors)
        base_prompt += f"""

上次生成不符合格式要求，请修正以下错误：
{error_text}

请重新生成。
"""

    return base_prompt


def start_node(state: GraphState) -> GraphState:
    """开始节点，初始化状态"""
    return {
        **state,
        "retry_count": 0,
        "max_retries": config.max_retries,
        "validation_errors": [],
        "is_valid": False,
    }


def build_prompt_node(state: GraphState) -> GraphState:
    """构建Prompt节点"""
    article = state["article"]
    errors = state["validation_errors"]

    system_prompt = _get_system_prompt(errors if errors else None)

    user_prompt = f"""请根据以下新闻，创作一篇币安广场推文：

新闻标题: {article.title}

新闻内容: {article.content}
"""

    full_prompt = system_prompt + "\n\n" + user_prompt

    return {
        **state,
        "prompt": full_prompt,
    }


def call_llm_node(state: GraphState) -> GraphState:
    """调用LLM节点"""
    prompt = state["prompt"]

    llm = ChatOpenAI(
        model=config.llm_model,
        base_url=config.llm_base_url,
        api_key=config.llm_api_key,
        temperature=0.7,
    )

    result = llm.invoke(prompt)
    generated_text = str(result.content).strip()

    return {
        **state,
        "generated_text": generated_text,
        "retry_count": state["retry_count"] + 1,
    }


def validate_node(state: GraphState) -> GraphState:
    """格式校验节点"""
    text = state["generated_text"]
    errors: List[str] = []

    # 检查字符数
    length = len(text)
    if length < config.min_chars:
        errors.append(f"字符数 {length} 小于最小要求 {config.min_chars}")
    if length > config.max_chars:
        errors.append(f"字符数 {length} 大于最大要求 {config.max_chars}")

    # 检查话题标签数量
    hashtag_count = text.count("#")
    if hashtag_count > config.max_hashtags:
        errors.append(f"话题标签 #{hashtag_count} 个超过最大限制 {config.max_hashtags}")

    # 检查代币标签数量
    mention_count = text.count("$")
    if mention_count > config.max_mentions:
        errors.append(f"代币标签 ${mention_count} 个超过最大限制 {config.max_mentions}")

    is_valid = len(errors) == 0

    return {
        **state,
        "validation_errors": errors,
        "is_valid": is_valid,
    }


def should_retry_router(state: GraphState) -> str:
    """判断是否需要重试"""
    if state["is_valid"]:
        return "end"
    if state["retry_count"] < state["max_retries"]:
        return "retry"
    return "fail"


class TweetGenerator:
    """推文生成器，使用LangGraph编排工作流"""

    def __init__(self) -> None:
        # 构建图
        builder = StateGraph(GraphState)
        builder.add_node("start", start_node)
        builder.add_node("build_prompt", build_prompt_node)
        builder.add_node("call_llm", call_llm_node)
        builder.add_node("validate", validate_node)

        builder.set_entry_point("start")
        builder.add_edge("start", "build_prompt")
        builder.add_edge("build_prompt", "call_llm")
        builder.add_edge("call_llm", "validate")
        builder.add_conditional_edges(
            "validate",
            should_retry_router,
            {
                "end": END,
                "retry": "build_prompt",
                "fail": END,
            },
        )

        self.graph = builder.compile()

    def generate_tweet(self, article: Article) -> Tweet:
        """生成推文"""
        initial_state: GraphState = {
            "article": article,
            "prompt": "",
            "generated_text": "",
            "validation_errors": [],
            "retry_count": 0,
            "max_retries": config.max_retries,
            "is_valid": False,
        }

        result = self.graph.invoke(initial_state)

        return Tweet(
            content=result["generated_text"],
            article_url=article.url,
            generated_at=datetime.now(),
            validation_passed=result["is_valid"],
            validation_errors=result["validation_errors"],
        )
