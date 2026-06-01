from collections.abc import Callable
from typing import Any

from deepagents import create_deep_agent
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from binance_square_bot.config import get_config
from binance_square_bot.services.generation.models import TweetSourceItem
from binance_square_bot.services.generation.skills import select_skill_path
from binance_square_bot.services.generation.validator import TweetContentValidator

AgentFactory = Callable[..., Any]


SYSTEM_PROMPT = """You are a Binance Square crypto content writer.
Generate one publish-ready Chinese Binance Square post from the user's
structured payload.
Return only the final post text, without Markdown fences, labels, or explanations.
"""


class DeepAgentTweetGenerator:
    """Generate validated account-specific tweets with DeepAgents."""

    def __init__(self, agent_factory: AgentFactory | None = None) -> None:
        self._agent_factory = agent_factory or self._default_agent_factory

    def generate_for_account(
        self,
        item: TweetSourceItem,
        api_key_mask: str,
        account_index: int,
        api_key: str | None = None,
    ) -> str:
        del api_key  # Never include full API keys in prompts or agent invocations.

        config = get_config()
        validator = TweetContentValidator(
            min_chars=config.min_chars,
            max_chars=config.max_chars,
            max_hashtags=config.max_hashtags,
            max_mentions=config.max_mentions,
        )
        agent = self._create_agent(item, config)

        validation_error: str | None = None
        for attempt in range(config.max_retries):
            task = self._build_task(
                item=item,
                api_key_mask=api_key_mask,
                account_index=account_index,
                attempt=attempt,
                validation_error=validation_error,
            )
            result = agent.invoke({"messages": [{"role": "user", "content": task}]})
            content = self._extract_content(result)
            try:
                validator.validate(content)
            except ValueError as exc:
                validation_error = str(exc)
                continue
            return content.strip()

        error_detail = validation_error or "unknown validation error"
        raise ValueError(
            "DeepAgents generation failed after "
            f"{config.max_retries} attempts: {error_detail}"
        )

    def _create_agent(self, item: TweetSourceItem, config: Any) -> Any:
        skill_path = select_skill_path(item)
        return self._agent_factory(
            model=config.llm_model,
            system_prompt=SYSTEM_PROMPT,
            tools=[],
            skills=[str(skill_path)],
            config=config,
        )

    def _build_task(
        self,
        item: TweetSourceItem,
        api_key_mask: str,
        account_index: int,
        attempt: int,
        validation_error: str | None,
    ) -> str:
        payload = item.to_prompt_payload()
        parts = [
            "请基于以下结构化内容生成一条币安广场推文。",
            f"item_payload: {payload!r}",
            f"account_mask: {api_key_mask}",
            f"account_index: {account_index}",
            (
                "variation: 为这个账号生成独立角度和措辞，避免与其他账号重复；"
                f"这是第 {attempt + 1} 次尝试。"
            ),
        ]
        if validation_error:
            parts.append(f"上次生成不符合格式要求: {validation_error}")
        return "\n".join(parts)

    @staticmethod
    def _extract_content(result: Any) -> str:
        if isinstance(result, str):
            return result.strip()

        if isinstance(result, list):
            text_blocks = []
            for block in result:
                if isinstance(block, str):
                    text_blocks.append(block)
                elif isinstance(block, dict) and isinstance(block.get("text"), str):
                    text_blocks.append(block["text"])
            return "\n".join(text_blocks).strip()

        if isinstance(result, dict):
            messages = result.get("messages")
            if isinstance(messages, list) and messages:
                return DeepAgentTweetGenerator._extract_content(messages[-1])
            content = result.get("content")
            if content is not None:
                return DeepAgentTweetGenerator._extract_content(content)

        content = getattr(result, "content", None)
        if content is not None:
            return DeepAgentTweetGenerator._extract_content(content)

        return str(result).strip()

    @staticmethod
    def _default_agent_factory(**kwargs: Any) -> Any:
        config = kwargs.pop("config")
        model = ChatOpenAI(
            api_key=SecretStr(config.llm_api_key),
            base_url=config.llm_base_url,
            model=config.llm_model,
        )
        kwargs["model"] = model
        return create_deep_agent(**kwargs)
