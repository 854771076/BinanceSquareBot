# CLI命令规格设计

## 1. 命令概览

本项目使用 **Typer** 构建命令行接口。所有命令通过 `binance-square-bot` 入口访问。

| 命令 | 功能 | 是否必需 |
|------|------|----------|
| `run` | 执行一次完整的爬取-生成-发布流程 | ✅ 必需 |
| `clean` | 清空已处理URL数据库 | ⚙️ 管理命令 |
| `--version` | 显示版本号 | ✅ 标准 |
| `--help` | 显示帮助信息 | ✅ 标准 |

---

## 2. 详细命令设计

### 2.1 `binance-square-bot run`

**功能**: 执行一次完整流程：爬取新闻 → 去重 → 生成推文 → 发布推文。

**语法**:
```bash
binance-square-bot run [OPTIONS]
```

**选项**:

| 选项 | 类型 | 默认值 | 说明 |
|------|------|---------|------|
| `--dry-run` | boolean | False | 试运行模式：只爬取和生成，不实际发布 |
| `--limit` | int | None | 限制处理文章数量（用于测试） |

**示例**:
```bash
# 正常执行
binance-square-bot run

# 试运行（不发布）
binance-square-bot run --dry-run

# 限制只处理3篇文章
binance-square-bot run --limit 3
```

**输出** (Rich表格):

```
✨ BinanceSquareBot 执行完成

统计信息:
┌──────────────────┬──────┐
│ 爬取新闻总数    │  15  │
│ 去重后新文章    │   3  │
│ 生成成功        │   3  │
│ 发布成功        │   3  │
│ 发布失败        │   0  │
└──────────────────┴──────┘
```

**退出码**:
- `0`: 执行成功（即使部分文章发布失败，只要流程正常走完）
- `1`: 执行错误（配置错误、数据库错误等）

---

### 2.2 `binance-square-bot clean`

**功能**: 清空已处理URL数据库，重置去重记录。

**语法**:
```bash
binance-square-bot clean [OPTIONS]
```

**选项**:

| 选项 | 类型 | 默认值 | 说明 |
|------|------|---------|------|
| `--yes` | boolean | False | 跳过确认，直接清空 |

**示例**:
```bash
# 需要确认
binance-square-bot clean

# 直接清空
binance-square-bot clean --yes
```

**交互流程**:
```
? 确认要清空已处理URL数据库吗? 此操作不可恢复 [y/N]:
```

---

### 2.3 `binance-square-bot --version`

**功能**: 显示当前版本号。

**输出**:
```
BinanceSquareBot v1.0.0
```

---

### 2.4 `binance-square-bot --help`

**功能**: 显示帮助信息。Typer自动生成。

**输出示例**:
```
Usage: binance-square-bot [OPTIONS] COMMAND [ARGS]...

  BinanceSquareBot - 自动爬取Fn新闻生成币安广场推文

Options:
  --version  -v  Show the version and exit.
  --help     -h  Show this message and exit.

Commands:
  clean  清空已处理URL数据库
  run    执行一次完整爬取-生成-发布流程
```

---

## 3. 输出格式规范

### 3.1 成功消息

- 使用 **绿色** 文字
- 使用 Rich Panel 或 Rich Table 美化输出

### 3.2 错误消息

- 使用 **红色** 文字
- 清晰说明错误原因

### 3.3 进度展示

- 使用 Rich Progress 显示处理进度
- 显示当前处理到第几个文章/共几个

---

## 4. 环境变量配置

所有配置通过环境变量加载（pydantic-settings）：

| 环境变量 | 必需 | 说明 | 示例 |
|----------|------|------|------|
| `BINANCE_API_KEYS` | ✅ | 逗号分隔的币安API密钥 | `key1,key2,key3` |
| `FN_NEWS_URL` | ❌ | Fn新闻列表URL | `https://news.fn.gov/news` |
| `SQLITE_DB_PATH` | ❌ | SQLite数据库路径 | `data/processed_urls.db` |
| `LLM_MODEL` | ❌ | LLM模型名称 | `gpt-4o-mini` |
| `LLM_BASE_URL` | ❌ | LLM API Base URL | `https://api.openai.com/v1` |
| `LLM_API_KEY` | ✅ | LLM API密钥 | `sk-xxx` |

---

**文档版本**: v1.0.0
**生成时间**: 2026-04-14 22:26:00
**维护者**: AI Agent
