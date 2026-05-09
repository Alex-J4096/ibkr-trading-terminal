from __future__ import annotations

import asyncio
from pathlib import Path

from ibkr_tui.models import PositionSnapshot, QuoteSnapshot
from ibkr_tui.order_service import OrderRequest, OrderService
from ibkr_tui.risk import RiskManager
from ibkr_tui.state import AppStateStore
from ibkr_tui.storage.sqlite_store import SQLiteStore


class FakeIBClient:
    def __init__(self) -> None:
        self.market_calls: list[tuple[str, str, float, str, bool]] = []
        self.limit_calls: list[tuple[str, str, float, float, str, bool]] = []
        self.cancel_calls: list[int] = []

    async def place_market_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        tif: str = "DAY",
        outside_rth: bool = False,
    ) -> int:
        self.market_calls.append((symbol, side, quantity, tif, outside_rth))
        return 101

    async def place_limit_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        limit_price: float,
        tif: str = "DAY",
        outside_rth: bool = False,
    ) -> int:
        self.limit_calls.append((symbol, side, quantity, limit_price, tif, outside_rth))
        return 202

    async def cancel_order(self, order_id: int) -> None:
        self.cancel_calls.append(order_id)


def make_service(db_path: Path) -> tuple[OrderService, FakeIBClient, AppStateStore]:
    from ibkr_tui.config import Settings

    settings = Settings()
    settings.ibkr.readonly = False
    settings.risk.max_order_qty = 100
    settings.risk.max_order_value_usd = 5000
    settings.risk.max_daily_orders = 10
    settings.risk.cooldown_seconds = 0
    settings.trading.account_mode = "paper"
    client = FakeIBClient()
    state = AppStateStore()
    store = SQLiteStore(db_path)
    service = OrderService(client, RiskManager(settings), state, store)
    return service, client, state


def test_submit_market_order(tmp_path: Path) -> None:
    async def scenario() -> None:
        service, client, state = make_service(tmp_path / "app.db")
        await state.update_connection("connected", "test")
        await state.update_market_data_status("connected", "test")
        await state.merge_quotes(
            [QuoteSnapshot(symbol="AAPL", last_price=100, data_status="REALTIME")]
        )
        message = await service.submit_order(
            OrderRequest(symbol="AAPL", side="BUY", quantity=5, order_type="MKT")
        )
        assert client.market_calls == [("AAPL", "BUY", 5, "DAY", False)]
        assert "Submitted order 101" in message

    asyncio.run(scenario())


def test_submit_limit_order(tmp_path: Path) -> None:
    async def scenario() -> None:
        service, client, state = make_service(tmp_path / "app.db")
        await state.update_connection("connected", "test")
        await state.update_market_data_status("connected", "test")
        message = await service.submit_order(
            OrderRequest(
                symbol="AAPL",
                side="SELL",
                quantity=5,
                order_type="LMT",
                limit_price=123.45,
                outside_rth=True,
            )
        )
        assert client.limit_calls == [("AAPL", "SELL", 5, 123.45, "DAY", True)]
        assert "Submitted order 202" in message

    asyncio.run(scenario())


def test_flatten_position_submits_market_order(tmp_path: Path) -> None:
    async def scenario() -> None:
        service, client, state = make_service(tmp_path / "app.db")
        await state.update_connection("connected", "test")
        await state.update_market_data_status("connected", "test")
        await state.replace_positions(
            [PositionSnapshot(symbol="AAPL", quantity=10, average_cost=90)]
        )
        await state.merge_quotes(
            [QuoteSnapshot(symbol="AAPL", last_price=100, data_status="REALTIME")]
        )
        message = await service.flatten_position("AAPL")
        assert client.market_calls == [("AAPL", "SELL", 10, "DAY", False)]
        assert "Submitted flatten order 101" in message

    asyncio.run(scenario())


def test_cancel_order_delegates_to_ib_client(tmp_path: Path) -> None:
    async def scenario() -> None:
        service, client, _ = make_service(tmp_path / "app.db")
        message = await service.cancel_order(88)
        assert client.cancel_calls == [88]
        assert message == "Cancel requested for order 88"

    asyncio.run(scenario())


def test_flatten_all_positions_submits_one_order_per_position(tmp_path: Path) -> None:
    async def scenario() -> None:
        service, client, state = make_service(tmp_path / "app.db")
        await state.update_connection("connected", "test")
        await state.update_market_data_status("connected", "test")
        await state.replace_positions(
            [
                PositionSnapshot(symbol="AAPL", quantity=10, average_cost=90),
                PositionSnapshot(symbol="MSFT", quantity=-5, average_cost=200),
            ]
        )
        await state.merge_quotes(
            [
                QuoteSnapshot(symbol="AAPL", last_price=100, data_status="REALTIME"),
                QuoteSnapshot(symbol="MSFT", last_price=300, data_status="REALTIME"),
            ]
        )
        message = await service.flatten_all_positions()
        assert client.market_calls == [
            ("AAPL", "SELL", 10, "DAY", False),
            ("MSFT", "BUY", 5, "DAY", False),
        ]
        assert "AAPL#101" in message
        assert "MSFT#101" in message

    asyncio.run(scenario())


def test_cancel_all_orders_delegates_to_ib_client(tmp_path: Path) -> None:
    async def scenario() -> None:
        service, client, _ = make_service(tmp_path / "app.db")
        message = await service.cancel_all_orders([11, 12])
        assert client.cancel_calls == [11, 12]
        assert message == "Cancel requested for orders: 11, 12"

    asyncio.run(scenario())
