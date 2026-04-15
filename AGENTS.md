# AGENTS.md - AI Agent 开发指导文档

> 本文档由 fullstack-dev-workflow skill 自动生成，用于指导AI Agent（Claude Code、Cursor等）进行项目开发。所有技术栈和规范已锁定，AI Agent必须严格遵守。

---

## 项目概述

| 属性 | 内容 |
|------|------|
| 项目名称 | BinanceSquareBot |
| 项目类型 | AI应用 / CLI工具 |
| 项目规模 | 小型 |
| 核心目标 | 定时爬取Fn新闻，通过LLM生成符合规范的币安广场推文并自动发布 |
| 文档生成时间 | 2026-04-14 22:26:00 |

---

## 技术栈锁定（禁止更改）

> ⚠️ 以下技术栈已锁定，AI Agent不得擅自更改版本或替换技术方案

### 后端技术栈

| 技术 | 版本 | 用途 |
|------|------|------|
| Python | 3.11+ | 主开发语言 |
| Typer | 0.9+ | CLI命令行框架 |
| Rich | 13.x+ | 终端美观输出 |
| Pydantic | 2.x | 数据验证 |
| Pydantic Settings | 2.x | 环境变量配置管理 |
| SQLite | 3.x | 已爬取文章去重存储 |
| pytest | 8.x+ | 单元测试框架 |

### AI技术栈

| 技术 | 版本 | 用途 |
|------|------|------|
| LangChain | 0.2+ | LLM应用开发框架 |
| LangGraph | 0.1+ | Agent工作流编排 |

### 代码质量工具

| 技术 | 版本 | 用途 |
|------|------|------|
| Ruff | 0.5+ | Python代码检查 |
| Black | 24.x+ | 代码格式化 |
| mypy | 1.10+ | 静态类型检查 |

### 基础设施

| 技术 | 版本 | 用途 |
|------|------|------|
| 版本控制 | Git + GitHub | - | 代码版本管理 |
| CI/CD调度 | GitHub Actions | - | 每小时定时任务调度 |

---

## 架构模式

### 整体架构

| 属性 | 内容 |
|------|------|
| 架构模式 | 单体分层 + Agent编排 |
| 选择理由 | 项目规模小，功能单一，单体分层足够简单；AI工作流使用LangGraph编排 |

### 分层结构

```
├── CLI层 (cli.py)
│   ├── 命令行入口
│   ├── 参数解析
│   └── 调用服务层
├── 模型层 (models/)
│   ├── 文章数据模型
│   ├── 推文数据模型
│   └── 配置数据模型
├── 服务层 (services/)
│   ├── 新闻爬取服务 - 从Fn获取新闻列表
│   ├── AI推文生成服务 - LangGraph工作流
│   ├── 币安广场发布服务 - 调用API发布推文
│   └── 存储服务 - SQLite去重存储
├── 工具层 (utils/)
│   └── 通用工具函数
└── 配置层 (config.py)
    └── 加载环境变量配置
```

### 模块划分

| 模块名称 | 职责 | 核心文件路径 |
|----------|------|--------------|
| CLI入口 | 命令行解析、程序入口 | src/binance_square_bot/cli.py |
| 数据模型 | 数据结构定义 | src/binance_square_bot/models/ |
| 爬取服务 | Fn新闻爬取 | src/binance_square_bot/services/spider.py |
| 生成服务 | AI推文生成 (LangGraph) | src/binance_square_bot/services/generator.py |
| 发布服务 | 币安广场API调用 | src/binance_square_bot/services/publisher.py |
| 存储服务 | SQLite去重存储 | src/binance_square_bot/services/storage.py |
| 配置管理 | 环境变量加载 | src/binance_square_bot/config.py |

---

## 编码规范

### 命名规范

| 类别 | 规范 | 示例 |
|------|------|------|
| 文件命名 | snake_case | `fn_spider.py`, `storage_service.py` |
| 变量命名 | snake_case | `article_url`, `news_list` |
| 常量命名 | UPPER_SNAKE_CASE | `MAX_RETRY_COUNT`, `DEFAULT_HOUR_INTERVAL` |
| 类/模型命名 | PascalCase | `Article', `TweetGenerator` |
| 函数命名 | snake_case + 动词开头 | `fetch_news_list`, `generate_tweet` |
| 数据库表名 | snake_case（复数） | `articles`, `processed_urls` |
| 数据库字段 | snake_case | `url_md5`, `created_at` |

### 目录规范

```
src/
└── binance_square_bot/        # 主Python包
    ├── __init__.py
    ├── cli.py                 # CLI入口
    ├── config.py              # 配置管理
    ├── models/                # 数据模型
    │   ├── __init__.py
    │   ├── article.py
    │   └── tweet.py
    ├── services/              # 业务服务
    │   ├── __init__.py
    │   ├── spider.py
    │   ├── generator.py
    │   ├── publisher.py
    │   └── storage.py
    └── utils/                 # 工具函数
        ├── __init__.py
        └── hash.py

tests/                          # 测试代码
├── __init__.py
├── test_spider.py
├── test_generator.py
├── test_publisher.py
└── test_storage.py

.github/
└── workflows/                 # GitHub Actions定时任务
    └── run-bot.yml            # 每小时执行配置
```

### 代码风格

| 配置项 | 配置值 |
|--------|--------|
| 格式化工具 | Ruff + Black |
| 配置文件路径 | pyproject.toml |
| 自动格式化 | 开启 |
| Lint检查 | Ruff |
| 类型检查 | mypy |

### 注释规范

| 类型 | 规范 |
|------|------|
| 文件头注释 | 文件功能说明、创建时间 |
| 函数注释 | 参数说明、返回值说明 |
| 复杂逻辑注释 | 必须添加说明注释 |
| TODO注释 | 格式：`# TODO: [描述] - [负责人] - [日期]` |

---

## 安全规范

### 传输安全

| 规范项 | 要求 |
|--------|------|
| HTTPS | 强制HTTPS，爬取和API调用都使用HTTPS |
| 敏感数据传输 | API密钥通过HTTPS传输 |

### 认证授权

| 规范项 | 要求 |
|--------|------|
| API密钥存储 | 通过环境变量传入，不写入代码文件 |
| .gitignore | 确保.env文件已忽略 |

### 输入校验

| 规范项 | 要求 |
|--------|------|
| 参数类型校验 | Pydantic自动校验 |
| SQL注入防护 | 使用参数化查询，禁止字符串拼接SQL |

### 日志安全

| 规范项 | 要求 |
|--------|------|
| 敏感字段脱敏 | API密钥不记录到日志 |

---

## 数据库规范

### 表设计规范

| 规范项 | 要求 |
|--------|------|
| 主键 | 统一命名为 `id` |
| 时间字段 | `created_at` |

### 索引规范

| 规范项 | 要求 |
|--------|------|
| 主键索引 | 自动创建 |
| 唯一索引 | `url_md5` 字段需要唯一索引用于去重 |

---

## 测试规范

### 测试覆盖要求

| 测试类型 | 覆盖率要求 |
|----------|------------|
| 单元测试 | 核心业务逻辑100%覆盖 |

### 测试命名规范

| 测试类型 | 命名规范 |
|----------|----------|
| 单元测试 | `{模块名}.test.py` |

---

## 文档驱动开发规范

### 核心原则

| 原则 | 说明 |
|------|------|
| 文档先行 | 无文档不开发，无设计不编码 |
| 索引闭环 | 每层级目录必须有 `index.md` |
| 变更备份 | 任何修改前必须触发全量快照备份 |
| 关联同步 | 需求变更后必须同步所有下游文档 |
| 一致性校验 | 每环节完成后必须AI自检 |

### 文档目录结构

```
docs/
├── index.md                    # 根索引文档
├── 需求.md                     # 用户原始需求
├── doc-dependency-matrix.yaml  # 依赖矩阵
├── 00-requirements/            # 需求文档
│   ├── index.md
│   └── tech-selection-report.md
├── 01-requirements-standard/   # 需求标准化
├── 03-backend-design/          # 后端设计
├── 04-test-acceptance/         # 测试验收
├── plans/                      # 实施计划
│   ├── active/
│   ├── archived/
│   └── index.md
└── phase-check-reports/        # 阶段检查报告
```

### ID命名规范

| ID类型 | 格式 | 示例 |
|--------|------|------|
| 需求ID | REQ-{模块}-{序号} | REQ-BOT-001 |
| 接口ID | API-{模块}-{序号} | API-SPIDER-001 |
| 变更单号 | CHG-{日期}-{序号} | CHG-20260414-001 |

---

## 禁止事项

> ⚠️ AI Agent必须严格遵守以下禁止事项，违反将导致流程终止

1. **禁止擅自更改技术栈**：所有技术选型已锁定，不得替换框架、库版本
2. **禁止超范围开发**：所有开发必须严格限定在需求文档范围内
3. **禁止自由发挥**：所有代码必须基于设计文档，不得自行设计
4. **禁止跳过文档**：禁止先写代码后补文档
5. **禁止跨环节执行**：上一环节未通过校验不得进入下一环节
6. **禁止修改历史版本**：历史备份文件只读，不得修改
7. **禁止无备份修改**：任何文档/代码修改前必须先备份

---

## 开发流程速查

### 新功能开发流程

```
1. 需求文档化（阶段1）→ prd.md, srs.md
2. 架构设计（阶段2.1）→ system-architecture.md
3. 后端设计（阶段2.3）→ 接口设计文档
4. 代码开发（阶段3）→ 基于设计文档编码
5. 测试验收（阶段4）→ 测试报告
```

### 需求变更流程

```
1. 变更申请 → 分配变更单号
2. 全量备份 → .version-history/
3. 影响分析 → 依赖矩阵查询
4. 文档更新 → 按优先级同步
5. 一致性校验 → 校验报告
6. 代码变更 → 基于新文档编码
```

---

## 常用命令

### 项目安装

```bash
# 使用pip
pip install -e .

# 使用poetry
poetry install
```

### 运行Bot

```bash
# 单次运行
binance-square-bot run
```

### 测试命令

```bash
# 单元测试
pytest

# 覆盖率报告
pytest --cov=src
```

### 代码检查

```bash
# Ruff lint检查
ruff check src/

# Ruff format格式化
ruff format src/

# mypy类型检查
mypy src/
```

---

**文档版本**: v1.0.0
**最后更新**: 2026-04-14
**维护者**: AI Agent 自动生成
