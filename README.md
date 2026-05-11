# IBKR Trading Terminal

一个基于 `Textual + ib_insync + IB Gateway` 的本地交易终端，实现用键盘驱动的快捷操作，完成持仓查看查看、下单、撤单和平仓。

## 功能

- 连接本地 `IB Gateway / TWS API`
- 显示账户状态、账户 ID、`Paper/Live` 模式、最后刷新时间
- `Positions` 持仓表，包含数量、最新价、成本、市值、浮盈亏和收益率
-  `Account Summary` 面板，包含净值、可用资金、购买力、现金、持仓数和订单数
-  `Watchlist` 行情表，包含最新价、涨跌额、涨跌幅和行情状态
-  `Orders` 订单表，包含订单 ID、方向、类型、数量、限价、状态、已成交和剩余数量
- 支持 `BUY / SELL` 下单，支持 `MKT` 市价单和 `LMT` 限价单
- 支持单持仓平仓、全持仓平仓、单订单撤单、全订单撤单
- 支持下单前确认；实盘模式是否追加输入 `CONFIRM` 强确认，可由配置文件`config.toml`中选项开关
- 支持最大单笔金额、最大单笔股数、日内订单数、同标的冷却时间等风控
- 行情不可用、IB 未连接、`readonly=true` 等场景下会阻止交易
- 所有交易相关事件写入本地 `sqlite`：`data/app.db -> trade_logs`
- 内置命令面板和键盘快捷键，适合纯键盘操作

## 主界面

```text
+----------------------------------------------------------------------------------+
| Header                                                   IBKR Trading Terminal   |
+---------------------------------------------+------------------------------------+
| Positions                                   | Account Summary                    |
| Symbol  Qty  Last   Avg     Mkt Value PnL   | Account: xxxxxxxx                  |
| NVDA    10   912.3  880.0   9,123.0   +323  | Currency: USD                      |
| AAPL    20   183.2  190.1   3,664.0   -138  | Net Liq: 100,000                   |
| TSM     15   158.4  151.0   2,376.0   +111  | Available: 82,500                  |
|                                             | Buying Power: 165,000              |
|                                             | Cash: 80,100                       |
|                                             | Positions: 3                       |
|                                             | Open Orders: 2                     |
+---------------------------------------------+------------------------------------+
| Watchlist                                   | Orders                             |
| Symbol  Last   Change   Chg%   Status       | ID   Sym   Side Type Qty Status    |
| AMD     142.2  +1.70    +1.2   REALTIME     | 101  NVDA  BUY  LMT  10  Submitted |
| MSFT    421.5  -1.31    -0.3   REALTIME     | 102  AAPL  SELL MKT   5  Filled    |
| TSLA    174.8  +3.44    +2.0   REALTIME     |                                     |
+----------------------------------------------------------------------------------+
| IB: CONNECTED | Quotes: CONNECTED | Account: DUxxxxxx | Mode: PAPER | ...       |
+----------------------------------------------------------------------------------+
| q Quit | r Refresh | Tab Next Panel | Enter View | b Buy | s Sell | x Flatten    |
| X Flatten All | c Cancel | C Cancel All | / Command                                 |
+----------------------------------------------------------------------------------+
```

### 界面说明

- `Positions`：核心持仓视图。用于查看当前持仓数量、成本、最新价、持仓市值和浮动盈亏，也是单持仓平仓的主要入口。
- `Account Summary`：账户摘要。用于快速判断净值、可用资金、购买力和现金情况，避免在下单前切到别的终端查账户状态。
- `Watchlist`：自选行情列表。用于跟踪配置里的标的价格变化，支持从这里直接对选中标的发起买入或卖出。
- `Orders`：订单状态面板。展示最近订单和当前开放订单的状态流转，包括 `Submitted / PartiallyFilled / Filled / Cancelled / ApiError`。
- `Status Bar`：全局状态栏。显示 IB 连接状态、行情连接状态、账户、模式、选中标的、刷新时间，以及最近消息或错误。
- `Footer / Key Hints`：底部快捷键提示。常用交易操作都可以从这里直接进入，不需要鼠标。

## 操作说明

- `Tab`：在 `Positions / Watchlist / Orders` 面板间切换焦点
- `j/k` 或方向键：在表格中上下移动
- `Enter`：查看当前选中持仓、行情或订单详情
- `b`：对选中标的发起买入
- `s`：对选中标的发起卖出
- `x`：平掉当前选中持仓
- `X`：平掉全部持仓，需要二次确认并输入 `CONFIRM`
- `c`：取消当前选中订单
- `C`：取消全部开放订单，需要二次确认并输入 `CONFIRM`
- `r`：立即刷新一次
- `/`：打开命令面板
- `q`：退出程序

## 运行

1. 首次拉取后先生成配置：

```bash
python scripts/generate_config.py
```

2. 初始化本地数据库：

```bash
python scripts/init_db.py
```

3. 编辑 `config.toml`，填写 `[market_data].api_key`，并确认 `[ibkr]` 的 `host` / `port` / `client_id`。
4. 启动本地 `IB Gateway` 或 `TWS API`。
5. 直接运行：

```bash
python run.py
```


## 说明

- 行情由 `Finnhub WebSocket` 提供，IB 主要负责账户、持仓和订单状态。
- 默认数据库路径为 `data/app.db`，交易日志表为 `trade_logs`。
- `config.toml` 中的 `[trading].confirm_live_orders` 用于控制 `Live` 模式是否启用额外强确认。
- 当 `confirm_live_orders = true` 时，`Live` 模式下单需要额外输入 `CONFIRM`；设为 `false` 时仅保留普通确认弹窗。
- `scripts/generate_config.py` 默认不会覆盖已有 `config.toml`；如需重建，使用 `--force`。
- `scripts/init_db.py` 默认初始化 `data/app.db`；如需重建，使用 `--force`。
- 周末或休市时可以验证连接、账户、持仓和订单状态刷新，但不能完整验证真实成交回报。
