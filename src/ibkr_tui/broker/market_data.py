from __future__ import annotations

from datetime import datetime, timezone

from ..models import QuoteSnapshot


def quote_from_finnhub_rest(symbol: str, payload: dict[str, object]) -> QuoteSnapshot:
    last_price = _as_float(payload.get("c"))
    previous_close = _as_float(payload.get("pc"))
    change = (
        last_price - previous_close
        if last_price is not None and previous_close not in (None, 0)
        else None
    )
    change_percent = (
        (change / previous_close) * 100
        if change is not None and previous_close not in (None, 0)
        else None
    )
    return QuoteSnapshot(
        symbol=symbol,
        last_price=last_price,
        previous_close=previous_close,
        change=change,
        change_percent=change_percent,
        data_status="REST",
        updated_at=datetime.now(timezone.utc),
    )


def quote_from_finnhub_trade(
    symbol: str, trade: dict[str, object], previous: QuoteSnapshot | None = None
) -> QuoteSnapshot:
    last_price = _as_float(trade.get("p"))
    previous_close = previous.previous_close if previous else None
    change = (
        last_price - previous_close
        if last_price is not None and previous_close not in (None, 0)
        else None
    )
    change_percent = (
        (change / previous_close) * 100
        if change is not None and previous_close not in (None, 0)
        else None
    )
    updated_at = datetime.now(timezone.utc)
    timestamp_ms = trade.get("t")
    if isinstance(timestamp_ms, (int, float)):
        updated_at = datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)

    return QuoteSnapshot(
        symbol=symbol,
        last_price=last_price,
        previous_close=previous_close,
        change=change,
        change_percent=change_percent,
        data_status="STREAMING",
        updated_at=updated_at,
    )


def _as_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
