from __future__ import annotations

from dataclasses import dataclass

from .broker.ib_client import IBGatewayClient
from .risk.risk_manager import RiskManager
from .state import AppStateStore


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
    ) -> None:
        self.ib_client = ib_client
        self.risk_manager = risk_manager
        self.state = state

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
        return (
            f"Submitted order {order_id}: {request.side} {request.quantity:g} "
            f"{request.symbol} {request.order_type} {request.tif}"
            f"{' outsideRth' if request.outside_rth else ''}"
        )

    async def flatten_position(self, symbol: str) -> str:
        snapshot = await self.state.snapshot()
        result = self.risk_manager.validate_flatten(snapshot, symbol=symbol)
        if not result.ok:
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
        return f"Submitted flatten order {order_id}: {side} {abs(position.quantity):g} {symbol}"

    async def cancel_order(self, order_id: int) -> str:
        await self.ib_client.cancel_order(order_id)
        return f"Cancel requested for order {order_id}"
