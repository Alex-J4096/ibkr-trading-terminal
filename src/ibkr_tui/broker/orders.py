from __future__ import annotations

from collections.abc import Iterable

from ib_insync import Trade

from ..models import OrderSnapshot


TERMINAL_STATUSES = {"Filled", "Cancelled", "ApiError"}


def normalize_order_status(status: str, *, filled: float, remaining: float) -> str:
    normalized = (status or "").strip().lower()
    if normalized in {"apicancelled", "cancelled", "pendingcancel"}:
        return "Cancelled"
    if normalized in {"inactive"}:
        return "ApiError"
    if filled > 0 and remaining > 0:
        return "PartiallyFilled"
    if normalized == "filled" or (filled > 0 and remaining <= 0):
        return "Filled"
    if normalized in {"presubmitted", "submitted", "pendingsubmit"}:
        return "Submitted"
    if normalized in {"pendingapi", "api pending"}:
        return "Created"
    return status or "Unknown"


def build_orders(trades: Iterable[Trade]) -> list[OrderSnapshot]:
    snapshots: list[OrderSnapshot] = []
    for trade in trades:
        contract = trade.contract
        order = trade.order
        status = trade.orderStatus
        filled = float(status.filled)
        remaining = float(status.remaining)
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
                status=normalize_order_status(
                    status.status,
                    filled=filled,
                    remaining=remaining,
                ),
                filled=filled,
                remaining=remaining,
                avg_fill_price=(
                    float(status.avgFillPrice) if status.avgFillPrice else None
                ),
                created_at=getattr(trade.log[0], "time", None) if trade.log else None,
                updated_at=getattr(trade.log[-1], "time", None) if trade.log else None,
            )
        )
    return merge_order_snapshots(snapshots)


def merge_order_snapshots(orders: Iterable[OrderSnapshot]) -> list[OrderSnapshot]:
    merged: dict[int, OrderSnapshot] = {}
    for order in orders:
        existing = merged.get(order.order_id)
        if existing is None or _is_newer_order(order, existing):
            merged[order.order_id] = order
    return sorted(merged.values(), key=_order_sort_key)


def _is_newer_order(candidate: OrderSnapshot, current: OrderSnapshot) -> bool:
    candidate_updated = candidate.updated_at or candidate.created_at
    current_updated = current.updated_at or current.created_at
    if candidate_updated and current_updated:
        return candidate_updated >= current_updated
    if candidate_updated:
        return True
    if current_updated:
        return False
    return _status_rank(candidate.status) >= _status_rank(current.status)


def _order_sort_key(order: OrderSnapshot) -> tuple[int, str, int]:
    return (_status_rank(order.status), order.symbol, -order.order_id)


def _status_rank(status: str) -> int:
    if status in TERMINAL_STATUSES:
        return 1
    return 0
