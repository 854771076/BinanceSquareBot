# CI流水线设计 (GitHub Actions)

## 1. 触发条件

### 1.1 定时触发（主用）

每小时整点执行一次：

```yaml
on:
  schedule:
    - cron: "0 * * * *"
```

### 1.2 手动触发

支持手动工作流触发：

```yaml
  workflow_dispatch:
```

---

## 2. 环境变量配置

GitHub Secrets 中配置以下密钥：

| Secret 名称 | 说明 | 示例 |
|------------|------|------|
| `BINANCE_API_KEYS` | 逗号分隔的币安API密钥 | `key1,key2` |
| `LLM_API_KEY` | LLM API密钥 | `sk-xxx` |
| `LLM_BASE_URL` | LLM API Base URL（可选，默认OpenAI） | `https://api.openai.com/v1` |

---

## 3. Job 设计

### 3.1 Job: `run-bot`

```yaml
run-bot:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4

    - name: Set up Python
      uses: actions/setup-python@v5
      with:
        python-version: "3.11"

    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install poetry
        poetry install

    - name: Run bot
      env:
        BINANCE_API_KEYS: ${{ secrets.BINANCE_API_KEYS }}
        LLM_API_KEY: ${{ secrets.LLM_API_KEY }}
        LLM_BASE_URL: ${{ secrets.LLM_BASE_URL }}
      run: |
        poetry run binance-square-bot run
```

---

## 4. 权限配置

不需要特殊权限，默认权限足够：

```yaml
permissions:
  contents: read
```

---

## 5. 超时设置

```yaml
jobs:
  run-bot:
    timeout-minutes: 30
```

30分钟超时足够处理所有新闻。

---

## 6. 失败通知

可以配置 Slack 通知（可选）：

```yaml
  - name: Notify on failure
    if: failure()
    uses: slackapi/slack-github-action@v1
    with:
      slack-message: "BinanceSquareBot执行失败: ${{ job.status }}\nWorkflow: ${{ github.workflow }} @ ${{ github.event.pull_request.head.label || github.head_ref || github.ref }}"
    env:
      SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK_URL }}
```

---

**文档版本**: v1.0.0
**生成时间**: 2026-04-14 22:26:00
**维护者**: AI Agent
