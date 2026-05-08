from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from ..config import Settings
from ..models import AppStateSnapshot


@dataclass(slots=True)
class RiskCheckResult:
    ok: bool
    message: str


class RiskManager:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._order_timestamps: list[datetime] = []
        self._last_symbol_orders: dict[str, datetime] = {}

    def validate_order(
        self,
        snapshot: AppStateSnapshot,
        *,
        symbol: str,
        side: str,
        quantity: float,
        order_type: str,
        limit_price: float | None = None,
    ) -> RiskCheckResult:
        now = datetime.now(timezone.utc)
        self._prune(now)

        if self.settings.ibkr.readonly:
            return RiskCheckResult(False, "Trading disabled: readonly=true")
        if snapshot.connection_status != "connected":
            return RiskCheckResult(False, "Trading blocked: IB Gateway not connected")
        if quantity <= 0:
            return RiskCheckResult(False, "Trading blocked: quantity must be positive")
        if quantity > self.settings.risk.max_order_qty:
            return RiskCheckResult(
                False,
                f"Trading blocked: quantity exceeds max_order_qty={self.settings.risk.max_order_qty}",
            )
        if (
            order_type == "MKT"
            and not self.settings.trading.allow_market_orders
        ):
            return RiskCheckResult(False, "Trading blocked: market orders disabled")

        quote = snapshot.quotes.get(symbol)
        reference_price = limit_price if order_type == "LMT" else None
        if reference_price is None and quote is not None:
            reference_price = quote.last_price
        if reference_price is None or reference_price <= 0:
            return RiskCheckResult(False, f"Trading blocked: quote unavailable for {symbol}")

        notional = reference_price * quantity
        if notional > self.settings.risk.max_order_value_usd:
            return RiskCheckResult(
                False,
                "Trading blocked: order value exceeds "
                f"max_order_value_usd={self.settings.risk.max_order_value_usd:,.2f}",
            )

        if len(self._order_timestamps) >= self.settings.risk.max_daily_orders:
            return RiskCheckResult(
                False,
                "Trading blocked: daily order limit reached",
            )

        last_symbol_order = self._last_symbol_orders.get(symbol)
        cooldown = timedelta(seconds=self.settings.risk.cooldown_seconds)
        if last_symbol_order is not None and now - last_symbol_order < cooldown:
            return RiskCheckResult(
                False,
                f"Trading blocked: cooldown active for {symbol}",
            )

        if (
            snapshot.market_data_status != "connected"
            and order_type == "MKT"
        ):
            return RiskCheckResult(
                False,
                "Trading blocked: market data unavailable for market order",
            )

        return RiskCheckResult(
            True,
            f"{side} {quantity:g} {symbol} {order_type} passed risk checks",
        )

    def validate_flatten(
        self, snapshot: AppStateSnapshot, *, symbol: str
    ) -> RiskCheckResult:
        position = snapshot.positions.get(symbol)
        if position is None or position.quantity == 0:
            return RiskCheckResult(False, f"Trading blocked: no open position for {symbol}")
        side = "SELL" if position.quantity > 0 else "BUY"
        return self.validate_order(
            snapshot,
            symbol=symbol,
            side=side,
            quantity=abs(position.quantity),
            order_type="MKT",
        )

    def record_order(self, symbol: str) -> None:
        now = datetime.now(timezone.utc)
        self._order_timestamps.append(now)
        self._last_symbol_orders[symbol] = now

    def _prune(self, now: datetime) -> None:
        cutoff = now - timedelta(days=1)
        self._order_timestamps = [
            timestamp for timestamp in self._order_timestamps if timestamp >= cutoff
        ]
