# Financial Hub Postgres

PostgreSQL 数据库操作组件，为 Financial Hub 系统中的各爬虫提供统一的数据库交互接口。

## 安装

```bash
pip install git+https://github.com/用户名/financial_hub_postgres.git
```

## 快速开始

```python
import psycopg2
from financial_hub_postgres import FinancialHubClient

# 由用户自行管理数据库连接
conn = psycopg2.connect(
    host="127.0.0.1",
    port=5432,
    user="hub_user",
    password="hub_password",
    dbname="financial_hub",
)

client = FinancialHubClient(conn)

# 查询所有抓取目标
targets = client.get_crawl_targets()

# 按来源类型筛选
wechat_targets = client.get_crawl_targets(source_type="wechat")

# 只查启用的目标
enabled_targets = client.get_crawl_targets(enabled=True)

# 按 ID 查询单个目标
target = client.get_crawl_target_by_id(1)

# 用完后关闭连接（由调用方管理）
conn.close()
```

## 设计原则

- **连接外置**：本组件不管理数据库配置和连接生命周期，由调用方传入 `psycopg2` 连接句柄。
- **面向对象**：通过 `FinancialHubClient` 类提供所有操作，便于扩展。
- **数据模型**：查询结果以 dataclass 对象返回，类型清晰、IDE 友好。

## 项目结构

```
financial_hub_postgres/
├── setup.py
├── README.md
├── src/
│   └── financial_hub_postgres/
│       ├── __init__.py
│       ├── client.py       # 主客户端类
│       └── models.py       # 数据模型
├── tests/
│   └── test_get_crawl_targets.py
└── documents/
    └── 数据库表说明.md
```
