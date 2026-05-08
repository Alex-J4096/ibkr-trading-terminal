# IBKR TUI Trading Terminal

本仓库当前实现了开发计划第一阶段的基础骨架：

- Textual 主界面
- IB Gateway 自动连接
- 持仓、观察列表、挂单只读视图
- Finnhub 实时行情刷新
- 中央状态管理

## 运行

1. 准备 `config.toml`，可以从 `config.example.toml` 复制。
2. 准备 `FINNHUB_API_KEY`，或在 `config.toml` 里填写 `[market_data].api_key`。
3. 启动本地 IB Gateway 或 TWS API。
4. 直接运行：

```bash
python run.py
```

或：

```bash
PYTHONPATH=src python -m ibkr_tui.main
```

安装后也可以：

```bash
ibkr-tui
```

## 说明

- 行情由 Finnhub WebSocket 提供，IB 仅负责账户、持仓和挂单。
