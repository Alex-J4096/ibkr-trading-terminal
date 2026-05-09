from __future__ import annotations

from dataclasses import dataclass

from .config import infer_account_mode
from .broker.ib_client import IBGatewayClient
from .risk.risk_manager import RiskManager
from .state import AppStateStore
from .storage.sqlite_store import SQLiteStore, TradeLogEntry


@dataclass(slots=True)
class OrderRequest:
    symbol: str
    side: str
    quantity: float
    order_type: str
    tif: str = "DAY"
    outside_rth: bool = False
    limit_price: float | None = None


class OrderService:
    def __init__(
        self,
        ib_client: IBGatewayClient,
        risk_manager: RiskManager,
        state: AppStateStore,
        store: SQLiteStore,
    ) -> None:
        self.ib_client = ib_client
        self.risk_manager = risk_manager
        self.state = state
        self.store = store

    async def submit_order(self, request: OrderRequest) -> str:
        snapshot = await self.state.snapshot()
        result = self.risk_manager.validate_order(
            snapshot,
            symbol=request.symbol,
            side=request.side,
            quantity=request.quantity,
            order_type=request.order_type,
            limit_price=request.limit_price,
        )
        if not result.ok:
            self.store.log_trade_event(
                TradeLogEntry(
                    event_type="submit_order",
                    status="risk_rejected",
                    message=result.message,
                    symbol=request.symbol,
                    side=request.side,
                    order_type=request.order_type,
                    quantity=request.quantity,
                    limit_price=request.limit_price,
                    account_mode=infer_account_mode(self.risk_manager.settings),
                )
            )
            raise ValueError(result.message)

        if request.order_type == "MKT":
            order_id = await self.ib_client.place_market_order(
                request.symbol,
                request.side,
                request.quantity,
                request.tif,
                request.outside_rth,
            )
        elif request.order_type == "LMT" and request.limit_price is not None:
            order_id = await self.ib_client.place_limit_order(
                request.symbol,
                request.side,
                request.quantity,
                request.limit_price,
                request.tif,
                request.outside_rth,
            )
        else:
            raise ValueError(f"Unsupported order type {request.order_type}")

        self.risk_manager.record_order(request.symbol)
        message = (
            f"Submitted order {order_id}: {request.side} {request.quantity:g} "
            f"{request.symbol} {request.order_type} {request.tif}"
            f"{' outsideRth' if request.outside_rth else ''}"
        )
        self.store.log_trade_event(
            TradeLogEntry(
                event_type="submit_order",
                status="submitted",
                message=message,
                symbol=request.symbol,
                side=request.side,
                order_type=request.order_type,
                quantity=request.quantity,
                limit_price=request.limit_price,
                order_id=order_id,
                account_mode=infer_account_mode(self.risk_manager.settings),
            )
        )
        return message

    async def flatten_position(self, symbol: str) -> str:
        snapshot = await self.state.snapshot()
        result = self.risk_manager.validate_flatten(snapshot, symbol=symbol)
        if not result.ok:
            self.store.log_trade_event(
                TradeLogEntry(
                    event_type="flatten_position",
                    status="risk_rejected",
                    message=result.message,
                    symbol=symbol,
                    order_type="MKT",
                    account_mode=infer_account_mode(self.risk_manager.settings),
                )
            )
            raise ValueError(result.message)

        position = snapshot.positions[symbol]
        side = "SELL" if position.quantity > 0 else "BUY"
        order_id = await self.ib_client.place_market_order(
            symbol,
            side,
            abs(position.quantity),
            "DAY",
            False,
        )
        self.risk_manager.record_order(symbol)
        message = f"Submitted flatten order {order_id}: {side} {abs(position.quantity):g} {symbol}"
        self.store.log_trade_event(
            TradeLogEntry(
                event_type="flatten_position",
                status="submitted",
                message=message,
                symbol=symbol,
                side=side,
                order_type="MKT",
                quantity=abs(position.quantity),
                order_id=order_id,
                account_mode=infer_account_mode(self.risk_manager.settings),
            )
        )
        return message

    async def flatten_all_positions(self) -> str:
        snapshot = await self.state.snapshot()
        result = self.risk_manager.validate_flatten_all(snapshot)
        if not result.ok:
            self.store.log_trade_event(
                TradeLogEntry(
                    event_type="flatten_all",
                    status="risk_rejected",
                    message=result.message,
                    order_type="MKT",
                    account_mode=infer_account_mode(self.risk_manager.settings),
                )
            )
            raise ValueError(result.message)

        submitted: list[str] = []
        for symbol, position in snapshot.positions.items():
            if position.quantity == 0:
                continue
            side = "SELL" if position.quantity > 0 else "BUY"
            order_id = await self.ib_client.place_market_order(
                symbol,
                side,
                abs(position.quantity),
                "DAY",
                False,
            )
            self.risk_manager.record_order(symbol)
            submitted.append(f"{symbol}#{order_id}")

        if not submitted:
            raise ValueError("Trading blocked: no positions to flatten")
        message = f"Submitted flatten-all orders: {', '.join(submitted)}"
        self.store.log_trade_event(
            TradeLogEntry(
                event_type="flatten_all",
                status="submitted",
                message=message,
                order_type="MKT",
                account_mode=infer_account_mode(self.risk_manager.settings),
            )
        )
        return message

    async def cancel_order(self, order_id: int) -> str:
        await self.ib_client.cancel_order(order_id)
        message = f"Cancel requested for order {order_id}"
        self.store.log_trade_event(
            TradeLogEntry(
                event_type="cancel_order",
                status="submitted",
                message=message,
                order_id=order_id,
                account_mode=infer_account_mode(self.risk_manager.settings),
            )
        )
        return message

    async def cancel_all_orders(self, order_ids: list[int]) -> str:
        if not order_ids:
            raise ValueError("Trading blocked: no open orders to cancel")
        for order_id in order_ids:
            await self.ib_client.cancel_order(order_id)
        message = f"Cancel requested for orders: {', '.join(str(order_id) for order_id in order_ids)}"
        self.store.log_trade_event(
            TradeLogEntry(
                event_type="cancel_all_orders",
                status="submitted",
                message=message,
                account_mode=infer_account_mode(self.risk_manager.settings),
            )
        )
        return message
