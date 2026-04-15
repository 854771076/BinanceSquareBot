# 领域模型设计

## 1. 核心领域对象

### 1.1 Article (文章)

从Fn新闻网站爬取的新闻文章。

**属性**:

| 属性名 | 类型 | 可空 | 说明 |
|--------|------|------|------|
| title | str | ❌ | 新闻标题 |
| url | str | ❌ | 新闻链接 |
| content | str | ❌ | 新闻内容/摘要 |
| published_at | datetime | ✔️ | 发布时间 |

### 1.2 Tweet (推文)

LLM生成的币安广场推文。

**属性**:

| 属性名 | 类型 | 可空 | 说明 |
|--------|------|------|------|
| content | str | ❌ | 推文内容 |
| article_url | str | ❌ | 关联的原文链接 |
| generated_at | datetime | ❌ | 生成时间 |
| validation_passed | bool | ❌ | 格式校验是否通过 |
| validation_errors | List[str] | ❌ | 校验错误列表 |

### 1.3 ProcessedURL (已处理URL)

已经处理过的URL记录，用于增量去重。

**属性**:

| 属性名 | 类型 | 可空 | 说明 |
|--------|------|------|------|
| id | int | ❌ | 主键 |
| url_md5 | str | ❌ | URL的MD5哈希 |
| url | str | ❌ | 原始URL |
| created_at | datetime | ❌ | 创建时间 |
| processed | bool | ❌ | 是否已发布 |

### 1.4 Config (配置)

应用配置，从环境变量加载。

**属性**:

| 属性名 | 类型 | 可空 | 说明 |
|--------|------|------|------|
| binance_api_keys | List[str] | ❌ | 币安API密钥列表 |
| fn_news_url | str | ❌ | Fn新闻列表URL |
| sqlite_db_path | str | ❌ | SQLite数据库文件路径 |
| llm_model | str | ❌ | LLM模型名称 |
| llm_base_url | str | ❌ | LLM API base URL |
| llm_api_key | str | ❌ | LLM API密钥 |
| max_retries | int | ❌ | 生成推文最大重试次数，默认3 |
| min_chars | int | ❌ | 推文最小字符数，默认101 |
| max_chars | int | ❌ | 推文最大字符数，默认799 |
| max_hashtags | int | ❌ | 最大#话题标签数，默认2 |
| max_mentions | int | ❌ | 最大$代币标签数，默认2 |

### 1.5 PublishResult (发布结果)

币安广场API发布结果。

**属性**:

| 属性名 | 类型 | 可空 | 说明 |
|--------|------|------|------|
| success | bool | ❌ | 是否发布成功 |
| tweet_id | str | ✔️ | 发布成功后的推文ID |
| error_message | str | ✔️ | 失败时的错误信息 |
| api_key_index | int | ❌ | 使用的API密钥索引 |

---

## 2. 领域关系

```
Article (1)  ——→  Tweet (1)
    一篇文章生成一篇推文

Tweet (1)  ——→  PublishResult (1)
    一篇推文对应一次发布结果

Article (1)  ——→  ProcessedURL (1)
    一篇文章对应一条去重记录
```

---

## 3. Pydantic 模型定义大纲

```python
# src/binance_square_bot/models/article.py
from pydantic import BaseModel
from datetime import datetime

class Article(BaseModel):
    title: str
    url: str
    content: str
    published_at: datetime | None = None

# src/binance_square_bot/models/tweet.py
class Tweet(BaseModel):
    content: str
    article_url: str
    generated_at: datetime
    validation_passed: bool
    validation_errors: list[str] = []

# src/binance_square_bot/config.py
class Config(BaseSettings):
    binance_api_keys: list[str]
    fn_news_url: str = "https://news.fn.gov/news"  # 示例
    sqlite_db_path: str = "data/processed_urls.db"
    llm_model: str = "gpt-4o-mini"
    llm_base_url: str = "https://api.openai.com/v1"
    llm_api_key: str
    max_retries: int = 3
    min_chars: int = 101
    max_chars: int = 799
    max_hashtags: int = 2
    max_mentions: int = 2
```

---

**文档版本**: v1.0.0
**生成时间**: 2026-04-14 22:26:00
**维护者**: AI Agent
