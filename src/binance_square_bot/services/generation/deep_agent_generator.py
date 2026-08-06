import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from deepagents import create_deep_agent
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from binance_square_bot.config import get_config
from binance_square_bot.services.generation.models import TweetSourceItem
from binance_square_bot.services.generation.skills import (
    get_humanizer_skill_path,
    select_skill_path,
)
from binance_square_bot.services.generation.validator import TweetContentValidator

AgentFactory = Callable[..., Any]


@dataclass
class GeneratedPost:
    body: str
    title: str | None = None


SYSTEM_PROMPT = """You are a Binance Square crypto content writer.
Generate one publish-ready Chinese Binance Square post from the user's
structured payload.

For post_type=text/image/video return ONLY the post body text.

For post_type=article return EXACTLY two blocks separated by a blank line:
    TITLE: <article title, 10-100 chars>
    <blank line>
    <article body, 800-15000 Chinese chars, plain text with short paragraphs,
     no Markdown fences, use $TOKEN and #topic sparingly and only when on
     the provided whitelist>
Do not add any other labels or explanations.
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
    ) -> GeneratedPost:
        del api_key  # Never include full API keys in prompts or agent invocations.

        config = get_config()
        validator_kwargs = dict(
            min_chars=config.min_chars,
            max_chars=config.max_chars,
            max_hashtags=config.max_hashtags,
            max_mentions=config.max_mentions,
            article_min_chars=getattr(config, "article_min_chars", 800),
            article_max_chars=getattr(config, "article_max_chars", 15000),
            article_min_title=getattr(config, "article_min_title", 10),
            article_max_title=getattr(config, "article_max_title", 100),
            coin_whitelist=tuple(item.coin_tags),
            post_type=item.post_type,
        )
        skill_path = select_skill_path(item)
        agent = self._create_agent(skill_path, config, item)

        validation_error: str | None = None
        for attempt in range(config.max_retries):
            task = self._build_task(
                item=item,
                api_key_mask=api_key_mask,
                account_index=account_index,
                attempt=attempt,
                validation_error=validation_error,
                config=config,
            )
            raw = self._invoke_agent(
                agent,
                task,
                config,
                item=item,
                api_key_mask=api_key_mask,
                account_index=account_index,
                attempt=attempt,
                skill_path=skill_path,
            )
            title, body = self._split_article(raw, item)
            validator = TweetContentValidator(**validator_kwargs)
            try:
                validator.validate(body)
                validator.validate_title(title)
            except ValueError as exc:
                validation_error = str(exc)
                if getattr(config, "agent_trace_enabled", False):
                    print(
                        f"↳ Validation failed: {validation_error} "
                        f"(#={body.count('#')} $={body.count('$')})"
                    )
                continue
            if getattr(config, "agent_trace_enabled", False):
                print("↳ Validation passed")
            return GeneratedPost(body=body.strip(), title=title.strip() if title else None)

        error_detail = validation_error or "unknown validation error"
        raise ValueError(
            "DeepAgents generation failed after "
            f"{config.max_retries} attempts: {error_detail}"
        )

    @staticmethod
    def _split_article(raw: str, item: TweetSourceItem) -> tuple[str | None, str]:
        """For article posts, split the 'TITLE: ...\n\n<body>' response."""
        text = raw.strip()
        if item.post_type != "article":
            return None, text
        if text.upper().startswith("TITLE:"):
            head, _, rest = text.partition("\n")
            title = head.split(":", 1)[1].strip()
            return title, rest.strip()
        # Fallback: first non-empty line as title.
        lines = text.split("\n", 1)
        if len(lines) == 2 and len(lines[0]) <= 80:
            return lines[0].strip(), lines[1].strip()
        return None, text

    def _create_agent(self, skill_path: Any, config: Any, item: TweetSourceItem) -> Any:
        # Article posts use the dedicated long-form skill; image posts keep the
        # source skill but the prompt constrains length.
        from binance_square_bot.services.generation.skills import skills_root

        skills = [str(skill_path)]
        if item.post_type == "article":
            article_skill = skills_root() / "square_article"
            if article_skill.is_dir():
                skills.insert(0, str(article_skill))
        return self._agent_factory(
            model=config.llm_model,
            system_prompt=SYSTEM_PROMPT,
            tools=[],
            skills=skills,
            config=config,
        )

    def _invoke_agent(
        self,
        agent: Any,
        task: str,
        config: Any,
        *,
        item: TweetSourceItem,
        api_key_mask: str,
        account_index: int,
        attempt: int,
        skill_path: Any,
    ) -> str:
        payload = {"messages": [{"role": "user", "content": task}]}
        humanizer_skill_path = get_humanizer_skill_path()
        agent_skills = [str(skill_path), str(humanizer_skill_path)]
        if not getattr(config, "agent_trace_enabled", False):
            return self._extract_content(agent.invoke(payload))
        return self._invoke_agent_with_trace(
            agent,
            payload,
            item=item,
            api_key_mask=api_key_mask,
            account_index=account_index,
            attempt=attempt,
            max_retries=config.max_retries,
            skill_path=skill_path,
            agent_skills=agent_skills,
        )

    def _invoke_agent_with_trace(
        self,
        agent: Any,
        payload: dict[str, Any],
        *,
        item: TweetSourceItem,
        api_key_mask: str,
        account_index: int,
        attempt: int,
        max_retries: int,
        skill_path: Any,
        agent_skills: list[str],
    ) -> str:
        print(
            "🧠 Agent attempt "
            f"{attempt + 1}/{max_retries} "
            f"source={item.source_name} content_type={item.content_type} "
            f"item={item.identifier} account={api_key_mask} "
            f"account_index={account_index}"
        )
        self._print_skill_configuration_trace(skill_path, agent_skills)
        last_chunk = None
        printed_previews: set[str] = set()
        runtime_evidence_observed = False
        for chunk in agent.stream(payload, stream_mode="values"):
            last_chunk = chunk
            runtime_evidence_observed = (
                self._print_trace_chunk(chunk, printed_previews)
                or runtime_evidence_observed
            )
        if runtime_evidence_observed:
            print("↳ Runtime skill event: observed")
        else:
            print("↳ Runtime skill event: not exposed by stream")
        content = self._extract_content(last_chunk)
        print(f"↳ Raw output counts: #={content.count('#')} $={content.count('$')}")
        return content

    def _print_skill_configuration_trace(
        self,
        skill_path: Any,
        agent_skills: list[str],
    ) -> None:
        path = Path(str(skill_path))
        skill_file = path / "SKILL.md"
        exists = skill_file.is_file()
        size = 0
        digest = "missing"
        if exists:
            data = skill_file.read_bytes()
            size = len(data)
            digest = hashlib.sha256(data).hexdigest()[:12]

        print(f"↳ Skill configured: {path.name}")
        print(f"↳ Skill path: {path}")
        print(f"↳ SKILL.md exists={exists} size={size}")
        print(f"↳ Skill digest: {digest}")
        print(f"↳ Agent factory skills: {agent_skills}")

    def _print_trace_chunk(self, chunk: Any, printed_previews: set[str]) -> bool:
        message = self._latest_message_from_chunk(chunk)
        runtime_evidence_observed = self._print_tool_calls(message)
        role = self._message_role(message)
        if role in {"user", "human"}:
            return runtime_evidence_observed

        content = self._extract_content(message)
        if not content:
            return runtime_evidence_observed
        preview = " ".join(content.split())[:160]
        if preview in printed_previews:
            return runtime_evidence_observed
        printed_previews.add(preview)
        print(f"↳ Agent message: {preview}")
        return runtime_evidence_observed

    def _print_tool_calls(self, message: Any) -> bool:
        observed = False
        for tool_call in self._message_tool_calls(message):
            name = self._tool_call_name(tool_call)
            if name:
                print(f"↳ Tool call: {name}")
                observed = True
        return observed

    @staticmethod
    def _latest_message_from_chunk(chunk: Any) -> Any:
        if isinstance(chunk, dict):
            messages = chunk.get("messages")
            if isinstance(messages, list) and messages:
                return messages[-1]
        return chunk

    @staticmethod
    def _message_role(message: Any) -> str | None:
        if isinstance(message, dict):
            role = message.get("role") or message.get("type")
            return str(role).lower() if role else None
        role = getattr(message, "role", None) or getattr(message, "type", None)
        return str(role).lower() if role else None

    @staticmethod
    def _message_tool_calls(message: Any) -> list[Any]:
        if isinstance(message, dict):
            calls = message.get("tool_calls") or []
        else:
            calls = getattr(message, "tool_calls", []) or []
        return calls if isinstance(calls, list) else []

    @staticmethod
    def _tool_call_name(tool_call: Any) -> str | None:
        if isinstance(tool_call, dict):
            value = tool_call.get("name")
            return str(value) if value else None
        value = getattr(tool_call, "name", None)
        return str(value) if value else None

    def _build_task(
        self,
        item: TweetSourceItem,
        api_key_mask: str,
        account_index: int,
        attempt: int,
        validation_error: str | None,
        config: Any,
    ) -> str:
        payload = item.to_prompt_payload()
        parts = [
            "请基于以下结构化内容生成一条币安广场推文。",
            f"post_type: {item.post_type}",
            f"item_payload: {payload!r}",
            f"account_mask: {api_key_mask}",
            f"account_index: {account_index}",
            (
                "variation: 为这个账号生成独立角度和措辞，避免与其他账号重复；"
                f"这是第 {attempt + 1} 次尝试。"
            ),
        ]

        if item.post_type == "article":
            parts.append(
                "format_limits: 输出必须以 'TITLE: <标题>' 开头，空一行，再输出正文；"
                f"正文 {getattr(config, 'article_min_chars', 800)}-"
                f"{getattr(config, 'article_max_chars', 15000)} 字；"
                "小标题用纯文本，不要 Markdown 围栏。"
            )
        elif item.post_type == "image":
            parts.append(
                "format_limits: 这是图文帖，正文 1-799 字，作为图片的配文，"
                f"# 话题标签最多 {config.max_hashtags} 个。"
            )
        else:
            parts.append(
                "format_limits: "
                f"字符数范围: {config.min_chars}-{config.max_chars}；"
                f"# 话题标签最多 {config.max_hashtags} 个；"
                f"$ 代币标签最多 {config.max_mentions} 个；"
                f"最终输出中 `$` 符号数量不得超过 {config.max_mentions}。"
            )

        if item.coin_tags:
            parts.append(
                "coin_whitelist: 只允许使用这些 $TOKEN 标签："
                f"{', '.join('$' + t for t in item.coin_tags)}。"
                "出现任何其他 $XXX 都视为违规。"
            )
        else:
            parts.append(
                "coin_whitelist: 本 item 没有明确的代币白名单；"
                f"如要使用 `$TOKEN`，累计不超过 {config.max_mentions} 个，且必须是真实存在的主流币种符号，不能臆造。"
            )
        parts.append("不要为了覆盖多个项目而堆叠 `$TOKEN`。")

        if validation_error:
            parts.append(f"上次生成不符合格式要求: {validation_error}")
            parts.append("请修复上次错误，优先减少标签数量，不要新增额外 `$` 或 `#` 标签。")
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
