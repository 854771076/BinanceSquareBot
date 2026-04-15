# 系统架构设计

## 1. 架构模式选择

### 1.1 架构模式

**选择: 单体分层架构 + LangGraph Agent编排**

| 属性 | 选择 |
|------|------|
| 架构模式 | 单体分层 + Agent编排 |
| 选择理由 | 项目规模小，功能单一，单体分层足够简单清晰；AI工作流部分使用LangGraph做状态编排，满足重试和条件跳转需求 |

### 1.2 分层结构

```
┌─────────────────────────────────────────────────────────────────┐
│                              CLI层                                │
│  (cli.py) - 命令行入口，参数解析，调用主服务                     │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                        配置层                                      │
│  (config.py) - pydantic-settings 加载环境变量                     │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                       服务层                                       │
│  • SpiderService  - 爬取Fn新闻                                   │
│  • StorageService  - SQLite去重存储                               │
│  • TweetGenerator  - LangGraph工作流，LLM生成+格式校验           │
│  • PublisherService - 调用币安广场API发布推文                     │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                        模型层                                      │
│  (models/) - Pydantic数据模型定义: Article, Tweet                 │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                        工具层                                      │
│  (utils/) - 通用工具函数: MD5计算等                                │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                       数据存储                                      │
│  SQLite - 存储已处理URL MD5                                        │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. 模块划分

| 模块 | 职责 | 文件路径 | 依赖 |
|------|------|----------|------|
| CLI入口 | 命令行解析，程序主入口 | `src/binance_square_bot/cli.py` | config, services |
| 配置管理 | 加载环境变量配置 | `src/binance_square_bot/config.py` | pydantic-settings |
| 数据模型 | 文章、推文数据结构定义 | `src/binance_square_bot/models/*.py` | pydantic |
| 爬取服务 | Fn新闻HTML爬取和解析 | `src/binance_square_bot/services/spider.py` | models, utils |
| 存储服务 | SQLite去重存储 | `src/binance_square_bot/services/storage.py` | models |
| 推文生成服务 | LangGraph工作流，LLM生成+格式校验+重试 | `src/binance_square_bot/services/generator.py` | models, langchain, langgraph |
| 发布服务 | 调用币安广场API发布 | `src/binance_square_bot/services/publisher.py` | models |
| 工具函数 | MD5计算等通用工具 | `src/binance_square_bot/utils/*.py` | - |

---

## 3. LangGraph 工作流设计

### 3.1 工作流节点

```
┌─────────────────┐
│   start         │ 输入: Article
└────────┬────────┘
         ↓
┌─────────────────┐
│  build_prompt   │ 构建Prompt: system + user
└────────┬────────┘
         ↓
┌─────────────────┐
│  call_llm       │ 调用LLM生成推文
└────────┬────────┘
         ↓
┌─────────────────┐
│  validate       │ 格式校验（字符数、#数量、$数量）
└────────┬────────┘
         ↓
         ├─────────────────────┐
         │ 校验通过?            │
         ├─Yes──────→ end      │ 输出: Tweet (validation_passed=True)
         │ No                   │
         ↓                      │
┌─────────────────┐             │
│  check_retries  │ 检查重试次数 < 最大重试? │
└────────┬────────┘             │
         ↓                      │
         ├─Yes──────→ build_prompt  │ 返回，带上错误提示让LLM修正
         │ No                   │
         ↓                      │
┌─────────────────┐             │
│  fail           │─────────────┘ 输出: Tweet (validation_passed=False)
└─────────────────┘
```

### 3.2 状态定义

```python
class GraphState(TypedDict):
    article: Article          # 输入的文章
    prompt: str              # 构建后的Prompt
    generated_text: str      # LLM生成的文本
    validation_errors: List[str]  # 校验错误
    retry_count: int         # 当前重试次数
    max_retries: int         # 最大重试次数
    is_valid: bool          # 是否校验通过
```

### 3.3 节点说明

| 节点 | 功能 |
|------|------|
| start | 初始化状态 |
| build_prompt | 根据文章和之前的校验错误构建Prompt，如果是重试则带上错误提示 |
| call_llm | 调用LLM生成推文内容 |
| validate | 校验推文格式：字符数、#数量、$数量 |
| check_retries | 校验失败后检查是否可以重试 |
| end | 返回结果 |
| fail | 返回失败结果 |

---

## 4. 数据库设计

### 4.1 processed_urls 表

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | 主键 |
| url_md5 | TEXT | NOT NULL UNIQUE | URL的MD5哈希 |
| url | TEXT | NOT NULL | 原始URL |
| created_at | DATETIME | DEFAULT CURRENT_TIMESTAMP | 创建时间 |
| processed | BOOLEAN | DEFAULT FALSE | 是否已处理发布 |

### 4.2 索引

- 唯一索引: `url_md5`

---

## 5. 数据流

### 5.1 主数据流

```
GitHub Actions (定时)
    ↓
CLI entrypoint (binance-square-bot run)
    ↓
SpiderService.fetch_news_list() → List[Article]
    ↓
StorageService → 逐个检查url_md5
    ↓
过滤得到新文章列表 (未处理)
    ↓
遍历每个API密钥
    ↓
    遍历每个新文章
        ↓
        TweetGenerator.generate_tweet(article) → GraphState
        ↓
        如果校验通过
            ↓
            PublisherService.publish_tweet() → 发布
            ↓
            StorageService.mark_processed() → 标记已处理
        ↓
        如果校验失败
            ↓
            记录错误，跳过
    ↓
汇总发布结果 → Rich输出
    ↓
退出
```

---

## 6. 技术架构决策记录

| 决策项 | 决策内容 | 理由 |
|--------|----------|------|
| 数据库选择 | SQLite | 嵌入式，不需要额外服务，适合GitHub Actions环境，数据量小 |
| Agent编排 | LangGraph | 用户指定，原生支持状态管理、条件分支、重试，非常适合这个工作流 |
| CLI框架 | Typer + Rich | 用户指定，现代化Python CLI，自动帮助文档，美观输出 |
| 配置管理 | pydantic-settings | 用户指定，类型安全，自动加载环境变量 |
| 去重方式 | MD5 URL哈希 | 简单有效，占用空间小，查询快 |

---

**文档版本**: v1.0.0
**生成时间**: 2026-04-14 22:26:00
**维护者**: AI Agent
