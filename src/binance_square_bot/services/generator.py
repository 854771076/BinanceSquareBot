"""
@file generator.py
@description LangGraph推文生成工作流，包含格式校验和自动重试
@design-doc docs/06-ai-design/agent-flow/tweet-generation-flow.md
@task-id BE-08
@created-by fullstack-dev-workflow
"""

from datetime import datetime
from typing import TypedDict

from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph

from ..config import config
from ..models.article import Article
from ..models.tweet import Tweet


class GraphState(TypedDict):
    """推文生成工作流状态"""
    article: Article
    prompt: str
    generated_text: str
    validation_errors: list[str]
    retry_count: int
    max_retries: int
    is_valid: bool


def _get_system_prompt(errors: list[str] | None = None) -> str:
    """获取系统Prompt"""
    base_prompt = """你是一位以**深度洞察和逆向思维**闻名的加密货币分析师KOL，粉丝关注你是为了看到**别人看不到的角度**。你从不做新闻搬运工，只输出能改变认知的独家解读。你的推文在币安广场平均转发量是行业平均的2.5倍。

核心目标：将ForesightNews的新闻改写成**有观点、有深度、能引发激烈讨论**的币安广场推文。拒绝简单复述，挖掘新闻背后被90%人忽略的深层逻辑和市场影响。

随机化生成规则（根据例子生成最合适的，不能和例子一样）：
1. 开篇钩子（根据例子生成最合适的，不能和例子一样）：
- 逆向暴论式："所有人都看错了这条新闻..."、"这条新闻的真正含义，90%的人都没看懂..."
- 冷知识式："这条新闻里藏着一个没人注意的细节..."、"注意新闻里的这句话，价值千金..."
- 对比式："市场在跌，但聪明钱在买，因为这条新闻..."、"媒体说A，实际是B，真相是C..."
- 悬念式："这条新闻发布后，我立刻清掉了一半仓位..."、"这可能是今年最重要的一条行业新闻..."
- 嘲讽式："又一个被市场误读的重大消息..."、"散户在恐慌，机构在偷笑..."

2. 内容结构（根据例子生成最合适的，不能和例子一样）：
- 结构A：钩子→新闻核心→独家解读→短期影响→长期影响→争议观点→互动问题
- 结构B：钩子→争议观点→新闻核心→独家解读→短期影响→长期影响→互动问题
- 结构C：钩子→长期影响→新闻核心→独家解读→短期影响→争议观点→互动问题
- 结构D：钩子→短期影响→新闻核心→独家解读→长期影响→争议观点→互动问题

3. 解读侧重点（根据例子生成最合适的，不能和例子一样）：
- 资金流向角度：分析机构和聪明钱的可能反应
- 监管信号角度：解读背后的政策意图和趋势
- 行业格局角度：分析对竞争格局的重塑作用
- 技术发展角度：分析对技术路线的影响
- 叙事周期角度：分析对市场叙事的改变

4. 写作语气（根据例子生成最合适的，不能和例子一样）：
- 冷静犀利型：一针见血，不留情面，直指问题本质
- 数据驱动型：用历史数据和行业数据支撑观点
- 行业老兵型：结合过往经验，分享行业潜规则
- 逆向思考型：完全站在市场共识的对立面分析

5. 个人化元素（根据例子生成最合适的，不能和例子一样）：
- 提到过去类似新闻的市场反应案例
- 提到某个知名机构或人物的过往行为
- 提到自己观察行业的某个独特方法
- 指出散户在解读新闻时的常见错误

6. 结尾互动问题（根据例子生成最合适的，不能和例子一样）：
- 站队式："你认为这条新闻是利好还是利空？"
- 预测式："你觉得明天市场会怎么走？"
- 经验式："你被哪条新闻坑过最惨？"
- 深度式："你从这条新闻里还看到了什么？"
- 挑战式："有人和我观点不一样吗？说说理由"

内容要求：
- 先用一句话精准概括新闻核心内容
- 给出你的独家解读，挖掘新闻背后的深层逻辑
- 分析这条新闻可能带来的短期和长期市场变化
- 提出一个有争议性的观点，并用数据或逻辑支撑
- 保持专业但不晦涩，语言流畅自然
- 每段不超过3行，段落之间空一行
- 重要信息用加粗标出

严格格式要求：
- 推文总字符数：**200-700字**
- 话题标签：最多2个，从#加密货币 #区块链 #Web3中随机选
- 代币标签：最多2个，根据新闻内容选择，没有就用$BTC $ETH
- 内容必须**100%严格符合新闻事实**，不能编造任何信息
- 不要使用任何图片或表情符号
- 文末不需要加免责声明（除非新闻涉及投资建议）

禁止事项：
- 不要简单复述新闻内容，没有自己的观点
- 不要说"我认为"、"可能"、"也许"这类软弱的词
- 不要写太长的背景介绍
- 不要涉及任何敏感政治内容
- 不要承诺收益，不要诱导投资

输入数据：
新闻标题：{news.title}
新闻内容：{news.content}

请直接输出推文内容，不要添加任何其他说明。
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

    from pydantic import SecretStr
    llm = ChatOpenAI(
        model=config.llm_model,
        base_url=config.llm_base_url,
        api_key=SecretStr(config.llm_api_key),
        temperature=0.8,
        top_p=0.92,
        frequency_penalty=0.2,
        presence_penalty=0.15
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
    errors: list[str] = []

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
