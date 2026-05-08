from __future__ import annotations

import asyncio

from ibkr_tui.models import PositionSnapshot, QuoteSnapshot
from ibkr_tui.state import AppStateStore


def test_state_store_replaces_positions_and_quotes() -> None:
    async def scenario() -> None:
        store = AppStateStore()
        await store.replace_positions(
            [PositionSnapshot(symbol="AAPL", quantity=10, average_cost=100)]
        )
        await store.merge_quotes([QuoteSnapshot(symbol="AAPL", last_price=120)])
        snapshot = await store.snapshot()
        assert snapshot.selected_symbol == "AAPL"
        assert snapshot.positions["AAPL"].average_cost == 100
        assert snapshot.quotes["AAPL"].last_price == 120

    asyncio.run(scenario())
