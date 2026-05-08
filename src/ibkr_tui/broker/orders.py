from __future__ import annotations

from collections.abc import Iterable

from ib_insync import Trade

from ..models import OrderSnapshot


def build_orders(trades: Iterable[Trade]) -> list[OrderSnapshot]:
    snapshots: list[OrderSnapshot] = []
    for trade in trades:
        contract = trade.contract
        order = trade.order
        status = trade.orderStatus
        snapshots.append(
            OrderSnapshot(
                order_id=order.orderId,
                symbol=contract.symbol,
                account_id=order.account or "",
                side=order.action,
                order_type=order.orderType,
                quantity=float(order.totalQuantity),
                tif=order.tif or "DAY",
                outside_rth=bool(order.outsideRth),
                limit_price=float(order.lmtPrice) if order.lmtPrice else None,
                status=status.status,
                filled=float(status.filled),
                remaining=float(status.remaining),
                avg_fill_price=(
                    float(status.avgFillPrice) if status.avgFillPrice else None
                ),
                created_at=getattr(trade.log[0], "time", None) if trade.log else None,
                updated_at=getattr(trade.log[-1], "time", None) if trade.log else None,
            )
        )
    return sorted(snapshots, key=lambda item: (item.symbol, item.order_id))
