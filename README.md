# financial_hub_postgres

> Financial Hub 系统的 PostgreSQL 数据库操作组件。  
> 供各独立爬虫程序以 pip 依赖形式引入，提供统一的数据库交互接口。

---

## 安装

```bash
pip install git+https://github.com/LeXrLt/financial_hub_postgres.git
```

依赖: `psycopg2-binary>=2.9.0`，Python >= 3.8。

---

## 核心概念

- 本组件 **不管理数据库连接**。调用方负责创建和关闭 `psycopg2.connect()` 连接，将其传入 `FinancialHubClient`。
- 所有操作通过 `FinancialHubClient` 实例调用。
- 查询结果以 Python `dataclass` 对象返回（`CrawlTarget`、`CrawlRun`）。

---

## 初始化

```python
import psycopg2
from financial_hub_postgres import FinancialHubClient

conn = psycopg2.connect(host="...", port=5432, user="...", password="...", dbname="financial_hub")
client = FinancialHubClient(conn)

# ... 使用 client 进行操作 ...

conn.close()  # 调用方自行管理连接生命周期
```

---

## API 参考

### 1. 查询抓取目标

#### `client.get_crawl_targets(source_type=None, enabled=None) -> List[CrawlTarget]`

查询 `crawl_targets` 表，返回符合条件的目标列表。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `source_type` | `str` | 否 | 按来源类型筛选，如 `"substack"`、`"wechat"`、`"youtube"`、`"xiaoyuzhou"` |
| `enabled` | `bool` | 否 | 按启用状态筛选 |

```python
# 获取所有目标
targets = client.get_crawl_targets()

# 获取指定类型且启用的目标
targets = client.get_crawl_targets(source_type="substack", enabled=True)
```

#### `client.get_crawl_target_by_id(target_id) -> Optional[CrawlTarget]`

按主键 ID 查询单个目标。未找到时返回 `None`。

```python
target = client.get_crawl_target_by_id(1)
```

---

### 2. 爬虫生命周期 Hook

爬虫执行前后需分别调用对应的 hook 方法，用于记录运行日志、更新目标状态、写入系统事件、上报组件健康。

#### `client.notify_crawl_start(target_id, component_name, metadata=None) -> CrawlRun`

**在爬虫开始执行前调用。** 单事务内完成以下操作：

| 步骤 | 操作 |
|------|------|
| 1 | 向 `crawl_runs` 插入一条 `status='running'` 的记录 |
| 2 | 将 `crawl_targets.last_crawl_status` 更新为 `'running'` |
| 3 | 向 `system_events` 写入 `crawl_start` 事件 |
| 4 | UPSERT `component_status` 为 `'healthy'` |

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `target_id` | `int` | 是 | 抓取目标 ID |
| `component_name` | `str` | 是 | 爬虫组件名称，如 `"substack_crawler"` |
| `metadata` | `dict` | 否 | 附加到系统事件的额外信息 |

**返回值:** `CrawlRun` 对象。调用方必须保存 `run.id`，后续传给 `notify_crawl_end`。

```python
run = client.notify_crawl_start(target_id=1, component_name="substack_crawler")
# run.id 将在结束时使用
```

#### `client.notify_crawl_end(run_id, target_id, component_name, success, ...) -> None`

**在爬虫执行完成后调用。** 单事务内完成以下操作：

| 步骤 | 操作 |
|------|------|
| 1 | 更新 `crawl_runs`：写入最终状态、结束时间、统计数据、错误信息 |
| 2 | 更新 `crawl_targets`：写入 `last_crawl_at`、`last_crawl_status`、`last_error`，累加 `total_items` |
| 3 | 向 `system_events` 写入 `crawl_end`（成功）或 `crawl_error`（失败）事件 |
| 4 | UPSERT `component_status`：成功设为 `'healthy'`，失败设为 `'degraded'` |

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `run_id` | `int` | 是 | `notify_crawl_start` 返回的 `CrawlRun.id` |
| `target_id` | `int` | 是 | 抓取目标 ID |
| `component_name` | `str` | 是 | 爬虫组件名称 |
| `success` | `bool` | 是 | 本次执行是否成功 |
| `items_found` | `int` | 否 | 本次发现的数据条数，默认 `0` |
| `items_new` | `int` | 否 | 本次新增的数据条数，默认 `0` |
| `items_failed` | `int` | 否 | 本次处理失败的条数，默认 `0` |
| `error_message` | `str` | 否 | 失败时的错误详情 |
| `duration_ms` | `int` | 否 | 运行耗时（毫秒） |
| `metadata` | `dict` | 否 | 附加到系统事件的额外信息 |

```python
# 成功
client.notify_crawl_end(
    run_id=run.id, target_id=1, component_name="substack_crawler",
    success=True, items_found=10, items_new=3, duration_ms=5200,
)

# 失败
client.notify_crawl_end(
    run_id=run.id, target_id=1, component_name="substack_crawler",
    success=False, error_message="Connection timeout after 30s", duration_ms=30000,
)
```

---

## 完整使用流程

以下是一个爬虫程序接入本组件的标准流程：

```python
import time
import psycopg2
from financial_hub_postgres import FinancialHubClient

conn = psycopg2.connect(host="...", port=5432, user="...", password="...", dbname="financial_hub")
client = FinancialHubClient(conn)

# Step 1: 查询需要抓取的目标
targets = client.get_crawl_targets(source_type="substack", enabled=True)

for target in targets:
    # Step 2: 通知开始
    run = client.notify_crawl_start(target_id=target.id, component_name="substack_crawler")

    # Step 3: 执行爬虫逻辑
    start = time.time()
    try:
        items_found, items_new = do_crawl(target.target_identifier)  # 你的业务代码
        duration_ms = int((time.time() - start) * 1000)

        # Step 4a: 通知成功
        client.notify_crawl_end(
            run_id=run.id, target_id=target.id, component_name="substack_crawler",
            success=True, items_found=items_found, items_new=items_new, duration_ms=duration_ms,
        )
    except Exception as e:
        duration_ms = int((time.time() - start) * 1000)

        # Step 4b: 通知失败
        client.notify_crawl_end(
            run_id=run.id, target_id=target.id, component_name="substack_crawler",
            success=False, error_message=str(e), duration_ms=duration_ms,
        )

conn.close()
```

---

## 数据模型

### `CrawlTarget`

对应 `crawl_targets` 表。

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | `int` | 主键 |
| `source_type` | `str` | 数据来源类型 |
| `target_name` | `str` | 目标名称 |
| `target_identifier` | `str` | 目标标识符，爬虫用来定位数据源 |
| `enabled` | `bool` | 是否启用 |
| `cron_expression` | `str` | 抓取频率 cron 表达式 |
| `last_crawl_at` | `datetime \| None` | 最后抓取时间 |
| `last_crawl_status` | `str \| None` | 最后抓取状态: `pending` / `running` / `success` / `failed` |
| `last_error` | `str \| None` | 最后失败的错误信息 |
| `total_items` | `int` | 累计抓取数据条数 |
| `notes` | `str \| None` | 备注 |
| `created_at` | `datetime \| None` | 创建时间 |
| `updated_at` | `datetime \| None` | 更新时间 |

### `CrawlRun`

对应 `crawl_runs` 表。

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | `int` | 主键 |
| `target_id` | `int` | 关联的 `crawl_targets.id` |
| `status` | `str` | 运行状态: `running` / `success` / `failed` |
| `started_at` | `datetime \| None` | 开始时间 |
| `finished_at` | `datetime \| None` | 结束时间 |
| `items_found` | `int` | 发现条数 |
| `items_new` | `int` | 新增条数 |
| `items_failed` | `int` | 失败条数 |
| `error_message` | `str \| None` | 错误信息 |
| `duration_ms` | `int \| None` | 耗时（毫秒） |

---

## 涉及的数据库表

本组件操作以下 5 张表（详细结构见 `documents/数据库表说明.md`）：

| 表名 | 用途 | 本组件操作 |
|------|------|-----------|
| `crawl_targets` | 抓取目标 | 查询、更新状态 |
| `crawl_runs` | 运行日志 | 插入、更新 |
| `component_status` | 组件健康 | UPSERT |
| `system_events` | 系统事件 | 插入 |
| `data_stats` | 数据统计快照 | 暂未实现 |

---

## 项目结构

```
financial_hub_postgres/
├── setup.py                              # 包安装配置
├── README.md
├── src/
│   └── financial_hub_postgres/
│       ├── __init__.py                   # 导出: FinancialHubClient, CrawlTarget, CrawlRun
│       ├── client.py                     # FinancialHubClient 类，所有数据库操作入口
│       └── models.py                     # 数据模型: CrawlTarget, CrawlRun
└── tests/
    └── test_substack_crawler.py          # 模拟 Substack 爬虫完整执行流程
```
