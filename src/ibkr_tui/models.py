from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(slots=True)
class QuoteSnapshot:
    symbol: str
    last_price: float | None = None
    previous_close: float | None = None
    bid: float | None = None
    ask: float | None = None
    change: float | None = None
    change_percent: float | None = None
    data_status: str = "UNKNOWN"
    updated_at: datetime | None = None


@dataclass(slots=True)
class PositionSnapshot:
    symbol: str
    quantity: float
    average_cost: float
    last_price: float | None = None
    market_value: float | None = None
    unrealized_pnl: float | None = None
    pnl_percent: float | None = None
    currency: str = "USD"


@dataclass(slots=True)
class OrderSnapshot:
    order_id: int
    symbol: str
    account_id: str
    side: str
    order_type: str
    quantity: float
    status: str
    filled: float
    remaining: float
    tif: str = "DAY"
    outside_rth: bool = False
    limit_price: float | None = None
    avg_fill_price: float | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(slots=True)
class AccountSummarySnapshot:
    account_id: str = ""
    net_liquidation: float | None = None
    available_funds: float | None = None
    buying_power: float | None = None
    cash_value: float | None = None
    currency: str = "USD"


@dataclass(slots=True)
class AppStateSnapshot:
    connection_status: str = "disconnected"
    connection_detail: str = "Not connected"
    market_data_status: str = "disconnected"
    market_data_detail: str = "Finnhub not connected"
    account_summary: AccountSummarySnapshot = field(
        default_factory=AccountSummarySnapshot
    )
    positions: dict[str, PositionSnapshot] = field(default_factory=dict)
    quotes: dict[str, QuoteSnapshot] = field(default_factory=dict)
    orders: list[OrderSnapshot] = field(default_factory=list)
    selected_symbol: str | None = None
    selected_panel: str = "positions"
    last_error: str | None = None
    last_message: str | None = None
    last_refresh: datetime | None = None
