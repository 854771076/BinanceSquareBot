# BinanceSquareBot

自动爬取 ForesightNews 重要新闻，通过 LLM 生成币安广场推文并定时发布。

## 🚀 功能特性

- ✅ **每日增量爬取** - 每日自动爬取今日重要新闻，通过 SQLite 存储已处理 URL MD5 实现增量去重
- ✅ **多账号支持** - 支持配置多个币安 API 密钥，每个内容项会为每个可用账号生成不同文案并发布
- ✅ **AI 智能生成** - 使用 DeepAgents 和仓库内 `agent_skills/` 技能生成推文，支持格式校验失败自动重试
- ✅ **强制格式约束** - 字符数、话题标签 `#`、代币标签 `$` 按配置校验，符合币安广场规范
- ✅ **定时自动运行** - GitHub Actions 每小时自动执行
- ✅ **完整单元测试** - 所有模块覆盖单元测试，类型安全有保证
- ✅ **Polymarket 投资研报** - 自动获取 Polymarket 最新市场，筛选热门新市场和概率偏离机会，AI 生成投资研报并发布
- ✅ **Followin 热点/币种分析** - 自动获取 Followin 热门话题、资金异动币种、讨论最热币种，AI 生成观点型推文
- ✅ **限流发布** - 每个 API 密钥每日发布上限可配，`parallel` 可限制每轮进入发布阶段的内容项数量
- ✅ **内容项去重** - 按天按来源和内容 ID 去重，已发布过的 URL/ID 当天不会重复处理
- ✅ **账号独立文案** - 相同内容项会针对每个可用 API 密钥分别生成文案，避免多账号发布完全重复内容
- ✅ **随机选择发布** - 并行模式先随机选择内容项，再为账号生成推文，发布行为更自然，不像是机器刷屏

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
cp .env_example .env
```

编辑 `.env` 文件：

```env
# 币安API密钥列表（逗号分隔，支持多账号）
BINANCE_TARGET_API_KEYS=your-first-api-key,your-second-api-key

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
binance-square-bot polymarket-research scan

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

# 限制每轮处理的内容项数量（不是最终多账号推文总数）
binance-square-bot parallel --total-per-run 5

# 并行试运行
binance-square-bot parallel --dry-run

# 并行执行并指定哪些源启用/禁用
binance-square-bot parallel --workers 8 --no-fn --enable-polymarket
```

### GitHub Actions 定时运行

项目已预置 `.github/workflows/run-bot.yml`，配置为**每小时自动执行**。自动运行会爬取内容、生成推文、发布，并自动提交数据库变更回你的仓库，保持去重状态持久化。

#### 配置步骤

1. **在 GitHub 添加 Secrets**

   进入你的 GitHub 仓库 → Settings → **Secrets and variables** → Actions → New repository secret，添加以下密钥：

   | Secret Name                 | Value                                               | Required      |
   | --------------------------- | --------------------------------------------------- | ------------- |
   | `BINANCE_TARGET_API_KEYS` | 币安API密钥列表，逗号分隔，例如：`key1,key2` | ✅ Required   |
   | `LLM_API_KEY`             | OpenAI API 密钥（或兼容接口的密钥）                 | ✅ Required   |
   | `LLM_BASE_URL`            | LLM API 地址（如使用第三方接口）                    | ⚙️ Optional |
   | `LLM_MODEL`               | LLM 模型名称                                        | ⚙️ Optional |
2. **确认仓库权限**

   当前 workflow 已配置 `permissions: contents: write`，对于大多数情况可以直接工作。如果仍然遇到推送权限错误 `403 Permission denied`，需要创建个人访问令牌 (PAT)：

   - 创建 PAT：GitHub → Settings → Developer settings → Personal access tokens → Generate new token
   - 勾选 `repo` 权限范围，生成 token
   - 添加到仓库 Secrets：Name = `PAT`，Value = 你的 token
   - 完成后即可正常推送数据库变更

#### 工作流程

- **触发时机**：每小时第 30 分钟 (`30 * * * *`) + 支持手动触发 (Workflow dispatch)
- **运行超时**：30 分钟（足够完成处理）
- **冲突处理**：运行前自动拉取远程最新代码，处理分支冲突
- **失败重试**：推送失败最多重试 5 次，提高成功率
- **自动提交**：运行完成后自动提交 `data/app.db` 数据库变更

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
│           ├── storage.py       # SQLite存储去重和发布统计
│           ├── spider.py        # ForesightNews爬虫
│           ├── account_item_publisher.py # 按内容项和账号生成/发布
│           ├── concurrent_executor.py    # 并行执行编排器（源并行 + 内容项发布）
│           ├── cli/                      # CLI服务
│           │   └── parallel_cli.py       # 并行执行CLI服务
│           ├── generation/               # DeepAgents 生成、内容项模型、映射和校验
│           ├── source/                   # 各数据源适配器
│           │   ├── fn_source.py          # ForesightNews 源
│           │   ├── polymarket_source.py  # Polymarket 源
│           │   └── followin_source.py    # Followin 源
│           └── target/                   # 发布目标适配器
│               └── binance_target.py     # 币安广场目标
├── agent_skills/                # DeepAgents 写作技能（按来源/内容类型选择）
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
└── .env_example                 # 环境配置示例
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
- [DeepAgents](https://github.com/langchain-ai/deepagents) - 基于仓库技能的推文生成
- [LangChain](https://python.langchain.com/) - OpenAI 兼容 LLM 接入
- [pydantic-settings](https://docs.pydantic.dev/latest/) - 类型安全配置
- [curl-cffi](https://github.com/yifeikong/curl_cffi) - 绕过反爬
- [SQLite](https://www.sqlite.org/) - 嵌入式增量去重

## 📝 工作流程

### 并行执行模式（推荐）

```
启动 parallel 命令
  ↓
各数据源并行执行（FnNews、Calendar、Airdrop、Fundraising、Polymarket、Followin...）
  ↓
    ├─ 爬取最新内容
    ├─ 过滤已发布内容（按天按来源去重）
    └─ 映射为 TweetSourceItem 内容项
  ↓
聚合所有内容项（items_generated / items_fetched）
  ↓
按 source_name + content_type + identifier 去重
  ↓
检查并过滤当天已发布内容
  ↓
随机打乱 + 按 total_per_run 限制内容项数量
  ↓
AccountItemPublisher 遍历每个内容项和每个可用 API 密钥
  ↓
DeepAgentTweetGenerator 选择 agent_skills/ 中的技能，为该账号生成独立推文
  ↓
发布成功后标记内容项为已发布 + 统计输出
```

### 关键特性

- **内容项去重**：相同 `source_name + content_type + identifier` 只保留一条。
- **账号级生成**：每个选中的内容项会对每个可用 Binance API 密钥调用一次 DeepAgents 生成，账号之间文案不同。
- **内容项限额**：`total_per_run` 限制进入发布阶段的内容项数量；最终生成/发布的推文数取决于内容项数量和可用账号数量。
- **发布后标记**：内容项至少有一个账号发布成功后才标记为当天已发布；dry-run 只生成和打印，不发布也不增加计数。

## 📄 License

MIT License

## 🙏 致谢

 Inspired by the need for automated crypto news sharing on Binance Square.
