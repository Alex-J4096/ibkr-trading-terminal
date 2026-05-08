from __future__ import annotations

from collections.abc import Iterable

from ib_insync import AccountValue, Position

from ..models import AccountSummarySnapshot, PositionSnapshot, QuoteSnapshot


def build_account_summary(values: Iterable[AccountValue]) -> AccountSummarySnapshot:
    value_map = {item.tag: item for item in values}
    sample = next(iter(value_map.values()), None)
    currency = sample.currency if sample else "USD"
    account_id = sample.account if sample else ""
    return AccountSummarySnapshot(
        account_id=account_id,
        net_liquidation=_maybe_float(value_map.get("NetLiquidation")),
        available_funds=_maybe_float(value_map.get("AvailableFunds")),
        buying_power=_maybe_float(value_map.get("BuyingPower")),
        cash_value=_maybe_float(value_map.get("TotalCashValue")),
        currency=currency,
    )


def apply_account_id(
    summary: AccountSummarySnapshot, account_id: str | None
) -> AccountSummarySnapshot:
    if summary.account_id or not account_id:
        return summary
    summary.account_id = account_id
    return summary


def build_positions(
    positions: Iterable[Position], quotes: dict[str, QuoteSnapshot]
) -> list[PositionSnapshot]:
    snapshots: list[PositionSnapshot] = []
    for position in positions:
        symbol = position.contract.symbol
        quote = quotes.get(symbol)
        last_price = quote.last_price if quote else None
        market_value = last_price * position.position if last_price is not None else None
        pnl = (
            (last_price - position.avgCost) * position.position
            if last_price is not None
            else None
        )
        cost_basis = position.avgCost * position.position
        pnl_percent = (pnl / cost_basis * 100) if pnl is not None and cost_basis else None
        snapshots.append(
            PositionSnapshot(
                symbol=symbol,
                quantity=position.position,
                average_cost=position.avgCost,
                last_price=last_price,
                market_value=market_value,
                unrealized_pnl=pnl,
                pnl_percent=pnl_percent,
                currency=position.contract.currency or "USD",
            )
        )
    return sorted(snapshots, key=lambda item: item.symbol)


def _maybe_float(value: AccountValue | None) -> float | None:
    if value is None:
        return None
    try:
        return float(value.value)
    except (TypeError, ValueError):
        return None
