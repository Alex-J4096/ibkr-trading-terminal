# IBKR Trading Terminal

本仓库当前实现了开发计划第一阶段的基础骨架：

- 主界面
- IB Gateway 自动连接
- 持仓、观察列表、挂单、账户信息
- Finnhub 实时行情刷新
- 快速买入、卖出和平仓等交易功能

## 运行

1. 首次拉取后先生成配置：

```bash
python scripts/generate_config.py
```

2. 编辑 `config.toml`，填写 `[market_data].api_key`，并确认 `[ibkr]` 的 `host` / `port` / `client_id`。
3. 启动本地 IB Gateway 或 TWS API。
4. 直接运行：

```bash
python run.py
```

## 说明

- 行情由 Finnhub WebSocket 提供，IB 仅负责账户、持仓和挂单。
- `scripts/generate_config.py` 默认不会覆盖已有 `config.toml`；如需重建，使用 `--force`。
