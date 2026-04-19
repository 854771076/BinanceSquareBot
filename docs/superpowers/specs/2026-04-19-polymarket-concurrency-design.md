# Polymarket 生成阶段并发功能设计

## 概述

为 `polymarket_research_run` CLI命令添加生成阶段并发，加速多个市场研报的生成过程。由于LLM生成是IO密集型（等待网络响应），并发可以显著减少总执行时间。

## 需求背景

- 当前 `polymarket_research_run` 是顺序处理：一个生成完成才能开始下一个
- 每个生成需要等待LLM API响应，浪费大量等待时间
- 用户要求：**仅生成阶段并发**，生成完成后再顺序发布，保持发布频率限制

## 设计决策

### 并发方案选择

选择 **`concurrent.futures.ThreadPoolExecutor`** 方案：

- ✅ 实现简单，改动最小
- ✅ 对于IO密集型任务（LLM API调用）效果非常好
- ✅ 不需要大规模重构现有代码结构
- ✅ 保持顺序发布，遵守原有的发布间隔限制和API限流

### 默认并发数

默认 **3** 个并发，可通过环境变量 `MAX_CONCURRENT_GENERATIONS` 配置。

## 详细设计

### 1. 配置项新增 (`src/binance_square_bot/config.py`)

```python
# 并发生成配置
max_concurrent_generations: int = 3  # 最大并发生成数
```

### 2. 执行流程变更

**原流程：**
```
获取市场数据 -> 筛选出Top市场 -> for 循环:
  -> 顺序生成每个市场推文
  -> 立即发布
  -> 等待间隔
```

**新流程：**
```
获取市场数据 -> 筛选出Top市场
-> ThreadPoolExecutor 并发:
  -> 每个市场并行调用LLM生成推文
  -> 收集生成结果（成功/失败）
-> 对生成成功的推文: for 循环顺序发布:
  -> 发布到所有币安账号
  -> 记录已发布到数据库
  -> 等待发布间隔
```

### 3. 线程安全保证

| 组件 | 线程安全性 | 处理方式 |
|------|-----------|---------|
| `ResearchGenerator.generate_with_retry` | LLM调用只读实例变量 | 每个工作线程创建独立实例，完全避免共享状态 |
| `Storage` 数据库操作 | 每次操作新建sqlite连接，自包含 | sqlite原生支持多线程并发，每个操作独立，天然线程安全 |
| `BinancePublisher` | 只在顺序发布阶段使用 | 无并发访问，安全 |

### 4. 数据结构

并发生成完成后，收集结果为 `list[tuple[PolymarketMarket, Tweet]]` 只包含生成成功的市场和推文，然后进入顺序发布流程。

### 5. 错误处理

- 生成失败的市场会被记录错误信息，跳过发布
- 保持原有的统计输出格式：显示成功生成数、成功发布数

## 变更文件

1. `src/binance_square_bot/config.py` - 添加配置项
2. `src/binance_square_bot/cli.py` - 修改 `polymarket_research_run` 函数实现并发

## 验收标准

- [ ] 多个市场能够并行生成，总耗时明显减少
- [ ] 生成失败正确处理，不影响其他市场
- [ ] 发布仍保持顺序，遵守间隔限制
- [ ] 线程安全，数据库操作不出现竞争条件
- [ ] 可通过配置调整并发数
