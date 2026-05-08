from __future__ import annotations

import asyncio
from contextlib import suppress

from ib_insync import IB, Contract, LimitOrder, MarketOrder, Stock

from ..config import Settings
from ..models import AccountSummarySnapshot, OrderSnapshot, PositionSnapshot
from ..state import AppStateStore
from .account import apply_account_id, build_account_summary, build_positions
from .finnhub_client import FinnhubMarketDataClient
from .orders import build_orders


class IBGatewayClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.ib = IB()

    def is_connected(self) -> bool:
        return self.ib.isConnected()

    async def disconnect(self) -> None:
        if self.ib.isConnected():
            self.ib.disconnect()

    async def place_market_order(
        self, symbol: str, side: str, quantity: float
    ) -> int:
        await self._ensure_connected()
        contract = await self._qualify_stock(symbol)
        trade = self.ib.placeOrder(contract, MarketOrder(side, quantity))
        return trade.order.orderId

    async def place_limit_order(
        self, symbol: str, side: str, quantity: float, limit_price: float
    ) -> int:
        await self._ensure_connected()
        contract = await self._qualify_stock(symbol)
        trade = self.ib.placeOrder(contract, LimitOrder(side, quantity, limit_price))
        return trade.order.orderId

    async def cancel_order(self, order_id: int) -> None:
        await self._ensure_connected()
        trade = self._find_trade(order_id)
        if trade is None:
            raise ValueError(f"Open order {order_id} not found")
        self.ib.cancelOrder(trade.order)

    def primary_account_id(self) -> str:
        return next(iter(getattr(self.ib.wrapper, "accounts", [])), "")

    async def refresh_state(self, state: AppStateStore) -> list[str]:
        try:
            await self._ensure_connected()
            await state.update_connection(
                "connected",
                (
                    f"Connected to {self.settings.ibkr.host}:{self.settings.ibkr.port} "
                    f"(clientId={self.settings.ibkr.client_id})"
                ),
            )
            positions = await self._refresh_positions(state)
            account_summary = await self._refresh_account_summary()
            orders = await self._refresh_orders()

            await state.replace_positions(positions)
            await state.replace_account_summary(account_summary)
            await state.replace_orders(orders)
            return [position.symbol for position in positions]
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            await state.update_connection("error", "IB Gateway unavailable", str(exc))
            await self.disconnect()
            return []

    async def _ensure_connected(self) -> None:
        if self.ib.isConnected():
            return
        await self.ib.connectAsync(
            self.settings.ibkr.host,
            self.settings.ibkr.port,
            clientId=self.settings.ibkr.client_id,
            readonly=self.settings.ibkr.readonly,
            timeout=5,
        )
        self.ib.reqMarketDataType(1)

    async def _refresh_account_summary(self) -> AccountSummarySnapshot:
        return apply_account_id(
            build_account_summary(await self.ib.accountSummaryAsync()),
            self.primary_account_id(),
        )

    async def _refresh_positions(self, state: AppStateStore) -> list[PositionSnapshot]:
        positions = await self.ib.reqPositionsAsync()
        snapshot = await state.snapshot()
        quote_map = snapshot.quotes
        stock_positions = [
            position
            for position in positions
            if getattr(position.contract, "secType", "") == "STK"
        ]
        return build_positions(stock_positions, quote_map)

    async def _refresh_orders(self) -> list[OrderSnapshot]:
        trades = await self.ib.reqAllOpenOrdersAsync()
        return build_orders(trades)

    async def _qualify_stock(self, symbol: str) -> Contract:
        contracts = await self.ib.qualifyContractsAsync(Stock(symbol, "SMART", "USD"))
        if not contracts:
            raise ValueError(f"Unable to qualify symbol {symbol}")
        return contracts[0]

    def _find_trade(self, order_id: int):
        for trade in self.ib.openTrades():
            if trade.order.orderId == order_id:
                return trade
        for trade in self.ib.trades():
            if trade.order.orderId == order_id:
                return trade
        return None


class RefreshController:
    def __init__(
        self,
        ib_client: IBGatewayClient,
        market_data_client: FinnhubMarketDataClient,
        state: AppStateStore,
        watchlist: list[str],
    ) -> None:
        self.ib_client = ib_client
        self.market_data_client = market_data_client
        self.state = state
        self.watchlist = watchlist
        self._lock = asyncio.Lock()
        self._started = False

    async def start(self) -> None:
        if self._started:
            return
        await self.market_data_client.start(self.state, self.watchlist)
        self._started = True

    async def refresh(self) -> None:
        if self._lock.locked():
            return
        async with self._lock:
            symbols = await self.ib_client.refresh_state(self.state)
            await self.market_data_client.ensure_symbols(self.watchlist + symbols)
            if symbols:
                await self.market_data_client.refresh_reference_quotes(symbols)

    async def shutdown(self) -> None:
        with suppress(Exception):
            await self.market_data_client.shutdown()
        with suppress(Exception):
            await self.ib_client.disconnect()
