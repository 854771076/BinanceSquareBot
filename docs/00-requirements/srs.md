# 软件需求规格 (SRS)

## 1. 引言

### 1.1 目的
本文档定义BinanceSquareBot的详细软件需求规格，包括功能分解、数据设计、接口定义和行为描述。

### 1.2 范围
本软件是一个Python CLI应用，使用LangGraph编排AI工作流，实现定时爬取新闻、AI生成推文、自动发布到币安广场的全流程自动化。

### 1.3 定义、首字母缩写和缩略语

| 术语 | 定义 |
|------|------|
| MD5 | 消息摘要算法，用于对URL去重 |
| LLM | 大语言模型，用于生成推文内容 |
| Agent | AI智能体，本项目指LangGraph编排的工作流 |
| CLI | 命令行界面 |
| GitHub Actions | GitHub提供的CI/CD服务，用于定时调度 |

---

## 2. 功能需求

### 2.1 REQ-BOT-001 定时增量爬取Fn新闻

**功能描述**: 定时（通过GitHub Actions每小时）爬取Fn新闻列表，使用SQLite存储已处理文章URL的MD5哈希进行去重，只处理新增文章。

**输入**: 无（爬取目标URL固定或可配置）
**输出**: 新文章列表（未去重的文章）

**处理流程**:
1. 发送HTTP请求获取Fn新闻列表HTML
2. 解析HTML提取文章标题、链接、内容摘要
3. 对文章URL计算MD5哈希
4. 查询SQLite的`processed_urls`表检查是否已存在
5. 如果已存在 → 跳过
6. 如果不存在 → 插入MD5到数据库，添加到待处理列表
7. 返回待处理列表

**数据库设计**:
```sql
CREATE TABLE IF NOT EXISTS processed_urls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url_md5 TEXT NOT NULL UNIQUE,
    url TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    processed BOOLEAN DEFAULT FALSE
);
```

**去重逻辑**:
- 使用URL的MD5作为唯一键
- 唯一约束保证不会重复插入
- 增量爬取只保留历史记录，不删除

---

### 2.2 REQ-BOT-002 多API密钥轮询

**功能描述**: 从环境变量读取多个币安API密钥，逗号分隔，轮询使用每个密钥发布推文。

**输入**: 环境变量 `BINANCE_API_KEYS`，格式: `key1,key2,key3`
**输出**: 每个密钥对应发布结果列表

**处理流程**:
1. 读取环境变量 `BINANCE_API_KEYS`
2. 按逗号分割得到密钥列表
3. 修剪每个密钥的空白字符
4. 过滤掉空字符串
5. 遍历密钥列表，逐个用于发布

**配置设计**:
- 使用pydantic-settings管理配置
- 支持单个密钥也支持多个密钥

---

### 2.3 REQ-BOT-003 LLM推文生成

**功能描述**: 基于新闻内容，使用LangGraph + LangChain调用LLM生成符合格式要求的币安广场推文。

**输入**: 新闻标题 + 新闻内容/摘要
**输出**: 生成的推文文本

**Agent工作流设计** (LangGraph):
1. **节点1**: 输入新闻数据，构建Prompt
2. **节点2**: 调用LLM生成推文
3. **节点3**: 格式校验
4. **条件判断**: 格式通过 → 结束；格式不通过 → 重试节点
5. **重试节点**: 重新提示LLM修正格式，最多重试3次
6. 重试仍不通过 → 记录错误，跳过该条新闻

**Prompt设计**:
- 系统Prompt: 明确格式约束（字符数、#数量、$数量）
- 用户Prompt: 输入新闻标题和内容，要求生成吸引观众的推文

**模型配置**:
- 使用OpenAI API（或兼容OpenAI接口的服务）
- 模型、base_url通过环境变量配置

---

### 2.4 REQ-BOT-004 推文格式强制校验

**功能描述**: 对LLM生成的推文进行格式校验，不满足要求则重试。

**校验规则** (全部满足才通过):

| 规则 | 检查方法 |
|------|----------|
| 字符数 > 100 | `len(text) > 100` |
| 字符数 < 800 | `len(text) < 800` |
| `#` 标签数量 ≤ 2 | 统计文本中`#`字符出现次数 |
| `$` 标签数量 ≤ 2 | 统计文本中`$`字符出现次数 |

**重试策略**:
- 最大重试次数: 3次
- 每次重试给出明确的错误提示（例如："话题数量超过限制，当前3个，最多允许2个，请重新生成"）

---

### 2.5 REQ-BOT-005 币安广场API发布

**功能描述**: 调用币安广场REST API发布生成好的推文。

**输入**: API密钥，推文文本
**输出**: 发布结果（成功/失败，错误信息）

**API调用**:
- 根据用户提供的 `币安广场api.md` 文档实现
- 请求方法: POST
- 认证: Bearer token 或 API Key 认证
- 处理响应: 判断是否发布成功，记录结果

**错误处理**:
- 发布失败记录错误信息，继续处理下一条
- 不因为单条失败中断整个流程

---

### 2.6 REQ-BOT-006 CLI命令行接口

**功能描述**: 使用Typer构建CLI命令行接口。

**命令设计**:

| 命令 | 功能 | 说明 |
|------|------|------|
| `binance-square-bot run` | 执行一次完整爬取-生成-发布流程 | 主入口 |
| `binance-square-bot clean` | 清空已处理URL记录表 | 管理命令 |
| `binance-square-bot --version` | 显示版本号 |  |

**输出设计**:
- 使用Rich输出美观的进度和结果
- 成功绿色，错误红色

---

### 2.7 REQ-BOT-007 GitHub Actions调度

**功能描述**: 配置GitHub Actions Workflow，每小时自动执行一次。

**Workflow设计**:
- 触发条件:  schedule: cron: "0 * * * *" (每小时整点)
- 也支持手动触发 (workflow_dispatch)
- 设置Python环境，安装依赖，运行 `binance-square-bot run`
- 配置Secrets存储API密钥

---

## 3. 数据需求

### 3.1 数据模型

#### 3.1.1 Article 文章模型

| 字段 | 类型 | 说明 |
|------|------|------|
| title | str | 新闻标题 |
| url | str | 新闻链接 |
| content | str | 新闻内容/摘要 |
| published_at | datetime | 发布时间 |

#### 3.1.2 Tweet 推文模型

| 字段 | 类型 | 说明 |
|------|------|------|
| content | str | 推文内容 |
| article_url | str | 关联的原文链接 |
| generated_at | datetime | 生成时间 |
| validation_passed | bool | 格式校验是否通过 |
| validation_errors | List[str] | 校验错误列表 |

#### 3.1.3 ProcessedURL 已处理URL模型

| 字段 | 类型 | 说明 |
|------|------|------|
| id | int | 主键 |
| url_md5 | str | URL的MD5哈希 |
| url | str | 原始URL |
| created_at | datetime | 创建时间 |
| processed | bool | 是否已处理发布 |

### 3.2 数据库存储

- 数据库: SQLite
- 数据库文件路径: `data/processed_urls.db` (默认，可配置)
- 自动创建表结构，如果表不存在

---

## 4. 接口需求

### 4.1 内部模块接口

#### 4.1.1 SpiderService 爬取服务接口

```python
class SpiderService:
    def fetch_news_list(self) -> List[Article]
    # 获取新闻列表
```

#### 4.1.2 StorageService 存储服务接口

```python
class StorageService:
    def is_url_processed(self, url: str) -> bool
    def mark_url_processed(self, url: str) -> None
    def init_database(self) -> None
```

#### 4.1.3 TweetGenerator 推文生成服务接口

```python
class TweetGenerator:
    def generate_tweet(self, article: Article) -> Tweet
    # 生成推文，包含重试和校验
```

#### 4.1.4 PublisherService 发布服务接口

```python
class PublisherService:
    def publish_tweet(self, api_key: str, tweet: Tweet) -> PublishResult
    # 发布单条推文
```

### 4.2 外部接口

- Fn新闻网站: HTTP GET 获取HTML
- 币安广场API: HTTP POST 发布推文
- LLM API: OpenAI兼容接口 生成文本

---

## 5. 非功能需求

### 5.1 代码质量

- 类型提示: 全部代码使用类型提示，mypy检查通过
- 代码格式化: Black + Ruff
- 单元测试: pytest，核心逻辑覆盖率 > 80%

### 5.2 安全性

- API密钥通过环境变量传递，不写入代码
- .gitignore排除 `.env` 和 `*.db`
- 日志不记录API密钥

### 5.3 可配置性

- 所有可配置项通过环境变量配置
- 使用pydantic-settings自动加载

---

## 6. 需求追踪矩阵

| 需求ID | 对应PRD需求 | 模块 | 测试用例 |
|--------|-------------|------|----------|
| REQ-BOT-001 | REQ-BOT-001 | services/spider.py, services/storage.py | tests/test_spider.py, tests/test_storage.py |
| REQ-BOT-002 | REQ-BOT-002 | config.py | - |
| REQ-BOT-003 | REQ-BOT-003 | services/generator.py | tests/test_generator.py |
| REQ-BOT-004 | REQ-BOT-004 | services/generator.py | tests/test_generator.py |
| REQ-BOT-005 | REQ-BOT-005 | services/publisher.py | tests/test_publisher.py |
| REQ-BOT-006 | REQ-BOT-006 | cli.py | - |
| REQ-BOT-007 | REQ-BOT-007 | .github/workflows/ | - |

---

**SRS版本**: v1.0.0
**生成时间**: 2026-04-14 22:26:00
**维护者**: AI Agent
