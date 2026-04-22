# BinanceSquareBot

自动爬取 ForesightNews 重要新闻，通过 LLM 生成币安广场推文并定时发布。

## 🚀 功能特性

- ✅ **每日增量爬取** - 每日自动爬取今日重要新闻，通过 SQLite 存储已处理 URL MD5 实现增量去重
- ✅ **多账号支持** - 支持配置多个币安 API 密钥，每个 API 密钥都会遍历所有新闻发布
- ✅ **AI 智能生成** - 使用 LangGraph 工作流，支持格式校验失败自动重试
- ✅ **强制格式约束** - 字符数 101-799，话题标签 `#` ≤ 2，代币标签 `$` ≤ 2，符合币安广场规范
- ✅ **定时自动运行** - GitHub Actions 每小时整点自动执行
- ✅ **完整单元测试** - 所有模块覆盖单元测试，类型安全有保证
- ✅ **Polymarket 投资研报** - 自动获取 Polymarket 最新市场，筛选热门新市场和概率偏离机会，AI 生成投资研报并发布
- ✅ **Followin 热点/币种分析** - 自动获取 Followin 热门话题、资金异动币种、讨论最热币种，AI 生成观点型推文
- ✅ **限流发布** - 每小时发布上限可配，默认每小时发布总量上限 + 各来源独立配额控制
- ✅ **内容去重** - 按天按来源去重，已发布过的 URL/ID 当天不会重复生成和发布
- ✅ **随机选择发布** - 生成多篇推文后随机选择发布，发布行为更自然，不像是机器刷屏

## 📋 环境要求

- Python 3.11+
- 币安广场 API 密钥 ([如何获取?](https://www.binance.com/zh-CN/square/developer/openapi))
- OpenAI API 密钥 (或兼容 OpenAI 格式的 API)

## 🛠️ 安装

```bash
# 克隆项目
git clone https://github.com/your-username/BinanceSquareBot.git
cd BinanceSquareBot

# 安装依赖
pip install .
```

## ⚙️ 配置

复制环境配置示例文件：

```bash
cp .env_simple .env
```

编辑 `.env` 文件：

```env
# 币安API密钥列表 (JSON数组格式，支持多账号)
BINANCE_API_KEYS=["your-api-key-1", "your-api-key-2"]

# OpenAI API Key
LLM_API_KEY=sk-xxx

# 可选配置
# LLM_MODEL=gpt-4o-mini
# LLM_BASE_URL=https://api.openai.com/v1
# MAX_RETRIES=3
# MIN_CHARS=101
# MAX_CHARS=799
# MAX_HASHTAGS=2
# MAX_MENTIONS=2

# Polymarket 投资研报配置（可选）
# ENABLE_POLYMARKET=true
# POLYMARKET_HOST=https://clob.polymarket.com
# POLYMARKET_CHAIN_ID=137
# MIN_VOLUME_THRESHOLD=1000
```

## 🚀 使用

### 命令行运行

```bash
# 查看帮助
binance-square-bot --help

# 查看版本
binance-square-bot --version

# 试运行（只爬取和生成，不实际发布）
binance-square-bot run --dry-run

# 完整运行
binance-square-bot run

# 限制处理文章数量（用于测试）
binance-square-bot run --limit 5

# 清空已处理URL去重记录
binance-square-bot clean

# 扫描 Polymarket 市场显示热门候选（不生成不发布）
binance-square-bot polymarket-scan

# 生成并发布 Polymarket 投资研报
binance-square-bot polymarket-research run

# 试运行（只获取筛选和生成，不发布）
binance-square-bot polymarket-research run --dry-run

# Followin 热点话题（试运行）
binance-square-bot followin topics --dry-run

# Followin 资金异动币种（试运行）
binance-square-bot followin io-flow --dry-run

# Followin 讨论最热币种（试运行）
binance-square-bot followin discussion --dry-run

# Followin 完整运行（所有数据源）
binance-square-bot followin run

# 🚀 并行执行所有源（推荐）
binance-square-bot parallel --workers 4

# 并行试运行
binance-square-bot parallel --dry-run

# 并行执行并指定哪些源启用/禁用
binance-square-bot parallel --workers 8 --no-fn --enable-polymarket
```

### GitHub Actions 定时运行

项目已预置 `.github/workflows/run-bot.yml`，配置为**每小时整点自动执行**。自动运行会爬取新闻、生成推文、发布，并自动提交数据库变更回你的仓库，保持去重状态持久化。

#### 配置步骤

1. **在 GitHub 添加 Secrets**

   进入你的 GitHub 仓库 → Settings → **Secrets and variables** → Actions → New repository secret，添加以下密钥：

   | Secret Name | Value | Required |
   |-------------|-------|----------|
   | `BINANCE_API_KEYS` | 币安API密钥列表，JSON格式，例如：`["key1", "key2"]` | ✅ Required |
   | `LLM_API_KEY` | OpenAI API 密钥（或兼容接口的密钥） | ✅ Required |
   | `LLM_BASE_URL` | LLM API 地址（如使用第三方接口） | ⚙️ Optional |
   | `LLM_MODEL` | LLM 模型名称 | ⚙️ Optional |

2. **确认仓库权限**

   当前 workflow 已配置 `permissions: contents: write`，对于大多数情况可以直接工作。如果仍然遇到推送权限错误 `403 Permission denied`，需要创建个人访问令牌 (PAT)：

   - 创建 PAT：GitHub → Settings → Developer settings → Personal access tokens → Generate new token
   - 勾选 `repo` 权限范围，生成 token
   - 添加到仓库 Secrets：Name = `PAT`，Value = 你的 token
   - 完成后即可正常推送数据库变更

#### 工作流程

- **触发时机**：每小时整点 (`0 * * * *`) + 支持手动触发 (Workflow dispatch)
- **运行超时**：30 分钟（足够完成处理）
- **冲突处理**：运行前自动拉取远程最新代码，处理分支冲突
- **失败重试**：推送失败最多重试 5 次，提高成功率
- **自动提交**：运行完成后自动提交 `data/processed_urls.db` 数据库变更

推送代码后 GitHub Actions 自动启用。

## 📁 项目结构

```
BinanceSquareBot/
├── src/
│   └── binance_square_bot/
│       ├── __init__.py          # 版本信息
│       ├── cli.py               # CLI入口 (Typer)
│       ├── config.py            # 配置加载 (pydantic-settings)
│       ├── models/
│       │   ├── article.py       # Article数据模型
│       │   └── tweet.py         # Tweet数据模型
│       └── services/
│           ├── storage.py       # SQLite存储去重
│           ├── spider.py        # ForesightNews爬虫
│           ├── generator.py     # AI推文生成 (LangGraph)
│           ├── polymarket_fetcher.py       # Polymarket 数据获取
│           ├── polymarket_filter.py        # Polymarket 市场筛选打分
│           ├── research_generator.py      # Polymarket 投资研报生成
│           └── binance_publisher.py      # 币安广场发布服务（多API密钥）
├── tests/
│   ├── test_storage.py          # 存储服务测试
│   ├── test_generator.py        # 格式校验测试
│   ├── test_publisher.py        # 发布服务测试
│   ├── test_spider.py           # 爬虫测试
│   └── live_test_spider.py      # 爬虫真实API测试
├── .github/
│   └── workflows/
│       └── run-bot.yml          # GitHub Actions定时任务
├── pyproject.toml               # 项目配置
└── .env_simple                  # 环境配置示例
```

## 🧪 开发测试

```bash
# 运行单元测试
python -m pytest tests/ -v

# 运行类型检查
mypy src/

# 爬虫真实API测试
python -m tests.live_test_spider
```

## 🔧 技术栈

- [Typer](https://typer.tiangolo.com/) - 现代 CLI 框架
- [Rich](https://rich.readthedocs.io/) - 美观终端输出
- [LangGraph](https://langchain-ai.github.io/langgraph/) - AI 工作流编排
- [pydantic-settings](https://docs.pydantic.dev/latest/) - 类型安全配置
- [curl-cffi](https://github.com/yifeikong/curl_cffi) - 绕过反爬
- [SQLite](https://www.sqlite.org/) - 嵌入式增量去重

## 📝 工作流程

```
启动
  ↓
爬取 ForesightNews 今日重要新闻
  ↓
SQLite 去重过滤出新文章
  ↓
遍历 API 密钥
  ↓
遍历新文章
  ↓
LangGraph 生成推文:
    ├─ 构建 Prompt
    ├─ LLM 生成
    ├─ 格式校验
    ├─ 通过 → 发布
    └─ 失败 → 重试 (最多 MAX_RETRIES 次)
  ↓
统计输出结果
```

## 📄 License

MIT License

## 🙏 致谢

 Inspired by the need for automated crypto news sharing on Binance Square.
