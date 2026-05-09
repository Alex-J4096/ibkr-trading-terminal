from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from ibkr_tui.broker.orders import build_orders, merge_order_snapshots
from ibkr_tui.models import OrderSnapshot


def make_trade(
    *,
    order_id: int,
    symbol: str = "AAPL",
    side: str = "BUY",
    order_type: str = "MKT",
    quantity: float = 10,
    status: str = "Submitted",
    filled: float = 0,
    remaining: float = 10,
    limit_price: float = 0,
    updated_at: datetime | None = None,
):
    timestamp = updated_at or datetime.now(UTC)
    return SimpleNamespace(
        contract=SimpleNamespace(symbol=symbol),
        order=SimpleNamespace(
            orderId=order_id,
            account="DU123",
            action=side,
            orderType=order_type,
            totalQuantity=quantity,
            tif="DAY",
            outsideRth=False,
            lmtPrice=limit_price,
        ),
        orderStatus=SimpleNamespace(
            status=status,
            filled=filled,
            remaining=remaining,
            avgFillPrice=0,
        ),
        log=[SimpleNamespace(time=timestamp)],
    )


def test_build_orders_normalizes_partial_fill_status() -> None:
    orders = build_orders(
        [make_trade(order_id=1, status="Submitted", filled=3, remaining=7)]
    )
    assert orders[0].status == "PartiallyFilled"


def test_build_orders_normalizes_terminal_statuses() -> None:
    orders = build_orders(
        [
            make_trade(order_id=1, status="Filled", filled=10, remaining=0),
            make_trade(order_id=2, status="Cancelled", filled=0, remaining=10),
            make_trade(order_id=3, status="Inactive", filled=0, remaining=10),
        ]
    )
    assert {order.order_id: order.status for order in orders} == {
        1: "Filled",
        2: "Cancelled",
        3: "ApiError",
    }


def test_merge_order_snapshots_prefers_newer_terminal_state() -> None:
    now = datetime.now(UTC)
    merged = merge_order_snapshots(
        [
            OrderSnapshot(
                order_id=7,
                symbol="AAPL",
                account_id="DU123",
                side="BUY",
                order_type="MKT",
                quantity=10,
                status="Submitted",
                filled=0,
                remaining=10,
                updated_at=now,
            ),
            OrderSnapshot(
                order_id=7,
                symbol="AAPL",
                account_id="DU123",
                side="BUY",
                order_type="MKT",
                quantity=10,
                status="Filled",
                filled=10,
                remaining=0,
                updated_at=now + timedelta(seconds=1),
            ),
        ]
    )
    assert len(merged) == 1
    assert merged[0].status == "Filled"
