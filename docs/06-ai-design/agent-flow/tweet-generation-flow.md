# 推文生成工作流设计 (LangGraph)

## 1. 工作流概述

使用LangGraph编排推文生成工作流，支持格式校验和自动重试。

**目标**: 根据输入的新闻文章，生成符合格式要求的币安广场推文，如果格式不满足要求则自动重试（最多N次）。

---

## 2. 状态定义 (GraphState)

```python
from typing import TypedDict, List
from binance_square_bot.models.article import Article
from binance_square_bot.models.tweet import Tweet

class GraphState(TypedDict):
    """推文生成工作流状态"""

    # 输入：原始文章
    article: Article
    # 构建好的Prompt
    prompt: str
    # LLM生成的文本
    generated_text: str
    # 校验错误列表
    validation_errors: List[str]
    # 当前重试次数
    retry_count: int
    # 最大重试次数
    max_retries: int
    # 是否校验通过
    is_valid: bool
```

---

## 3. 节点定义

### 3.1 `start` - 开始节点

**功能**: 初始化状态

**输入**: 文章

**处理**:
- 设置 `retry_count = 0`
- 设置 `max_retries` 从配置读取
- 设置 `validation_errors = []`
- 设置 `is_valid = False`

**输出**: 初始化后的状态

---

### 3.2 `build_prompt` - 构建Prompt节点

**功能**: 根据文章和之前的错误构建Prompt

**处理逻辑**:
1. 如果是第一次生成 (`retry_count == 0`):
   - 使用系统Prompt + 用户Prompt，输入文章标题和内容
2. 如果是重试 (`retry_count > 0`):
   - 在Prompt末尾追加错误信息，要求LLM修正：
   ```
   上次生成不符合格式要求，请修正以下错误：
   {errors}
   请重新生成。
   ```

**Prompt模板**:

**系统Prompt**:
```
你是一位专业的加密货币内容创作者，需要将一篇新闻改写成吸引币安广场用户的推文。

严格遵守以下格式要求：
1. 推文总字符数必须大于100且小于800
2. 话题标签（#开头）最多允许2个
3. 代币标签（$开头）最多允许2个
4. 内容必须符合新闻事实，同时吸引观众点击阅读
```

**用户Prompt**:
```
请根据以下新闻，创作一篇币安广场推文：

新闻标题: {title}

新闻内容: {content}
```

**输出**: 构建好的Prompt存入 `state["prompt"]`

---

### 3.3 `call_llm` - 调用LLM节点

**功能**: 调用LLM生成推文文本

**处理**:
- 使用LangChain ChatOpenAI 调用LLM
- 输入Prompt
- 获取生成的文本

**输出**: 生成的文本存入 `state["generated_text"]`
- `retry_count += 1`

---

### 3.4 `validate` - 格式校验节点

**功能**: 校验生成的推文是否符合所有格式要求

**校验规则**:

| 规则 | 检查方法 |
|------|----------|
| 字符数检查 | `len(text) > min_chars and len(text) < max_chars` |
| 话题标签检查 | `text.count('#') <= max_hashtags` |
| 代币标签检查 | `text.count('$') <= max_mentions` |

**处理**:
1. 逐一检查所有规则
2. 收集不满足规则的错误信息到 `validation_errors`
3. 如果没有错误 → `is_valid = True`
4. 如果有错误 → `is_valid = False`

**输出**:
- `is_valid` 标记是否通过
- `validation_errors` 错误列表

---

### 3.5 `should_retry` - 条件判断：是否需要重试

**功能**: 判断是否需要重试

**条件路由**:

```
如果 is_valid == True → 转到 end 节点
如果 is_valid == False 且 retry_count < max_retries → 转到 build_prompt 节点重试
如果 is_valid == False 且 retry_count >= max_retries → 转到 fail 节点
```

---

### 3.6 `end` - 结束节点

**功能**: 返回成功结果

**输出**:
- `validation_passed = True`
- `content = generated_text`

---

### 3.7 `fail` - 失败节点

**功能**: 返回失败结果，记录所有错误

**输出**:
- `validation_passed = False`
- `content = generated_text`
- `validation_errors` 保留所有错误

---

## 4. 图结构

```
start → build_prompt → call_llm → validate → should_retry
                               ↓
                         ┌─────┴─────┐
                         ↓         ↓
                        end       should_retry → retry? Yes → build_prompt
                                   ↓
                                  No → fail
```

---

## 5. 伪代码

```python
builder = StateGraph(GraphState)
builder.add_node("start", start_node)
builder.add_node("build_prompt", build_prompt_node)
builder.add_node("call_llm", call_llm_node)
builder.add_node("validate", validate_node)
builder.add_node("end", end_node)
builder.add_node("fail", fail_node)

builder.set_entry_point("start")
builder.add_edge("start", "build_prompt")
builder.add_edge("build_prompt", "call_llm")
builder.add_edge("call_llm", "validate")
builder.add_conditional_edges(
    "validate",
    should_retry,
    {
        "retry": "build_prompt",
        "end": "end",
        "fail": "fail",
    }
)
builder.add_edge("end", END)
builder.add_edge("fail", END)

graph = builder.compile()
```

---

## 6. Prompt库

### 6.1 系统Prompt - PROMPT-SYS-001

**位置**: `docs/06-ai-design/prompt-library/system-prompts/prompt-sys-001.md`

**内容**:
```
你是一位专业的加密货币内容创作者，需要将一篇来自Fn的新闻改写成吸引币安广场用户的推文。

严格遵守以下格式要求：

1. 推文总字符数必须大于 100 且小于 800。当前生成结果是 {length} 个字符，请调整。
2. 话题标签（#开头）最多允许 2 个。当前生成结果包含 {hashtag_count} 个，请删除多余的话题标签。
3. 代币标签（$开头）最多允许 2 个。当前生成结果包含 {mention_count} 个，请删除多余的代币标签。
4. 内容必须符合新闻事实，不能编造信息。
5. 内容需要吸引观众，最后可以引导关注或讨论。

请直接输出推文内容，不要添加其他说明。
```

### 6.2 用户Prompt - PROMPT-USER-001

**位置**: `docs/06-ai-design/prompt-library/user-prompts/prompt-user-001.md`

**内容**:
```
请根据以下新闻，创作一篇币安广场推文：

新闻标题: {title}

新闻内容: {content}
```

---

**文档版本**: v1.0.0
**生成时间**: 2026-04-14 22:26:00
**维护者**: AI Agent
