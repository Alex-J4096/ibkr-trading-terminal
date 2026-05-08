from __future__ import annotations

import asyncio
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone

from .models import (
    AccountSummarySnapshot,
    AppStateSnapshot,
    OrderSnapshot,
    PositionSnapshot,
    QuoteSnapshot,
)


class AppStateStore:
    def __init__(self) -> None:
        self._state = AppStateSnapshot()
        self._lock = asyncio.Lock()

    async def snapshot(self) -> AppStateSnapshot:
        async with self._lock:
            return deepcopy(self._state)

    async def update_connection(
        self, status: str, detail: str, last_error: str | None = None
    ) -> None:
        async with self._lock:
            self._state.connection_status = status
            self._state.connection_detail = detail
            self._state.last_error = last_error
            self._state.last_refresh = datetime.now(timezone.utc)

    async def update_market_data_status(
        self, status: str, detail: str, last_error: str | None = None
    ) -> None:
        async with self._lock:
            self._state.market_data_status = status
            self._state.market_data_detail = detail
            self._state.last_error = last_error
            self._state.last_refresh = datetime.now(timezone.utc)

    async def replace_account_summary(self, summary: AccountSummarySnapshot) -> None:
        async with self._lock:
            self._state.account_summary = replace(summary)
            self._state.last_refresh = datetime.now(timezone.utc)

    async def replace_positions(self, positions: list[PositionSnapshot]) -> None:
        async with self._lock:
            self._state.positions = {position.symbol: replace(position) for position in positions}
            if positions and self._state.selected_symbol not in self._state.positions:
                self._state.selected_symbol = positions[0].symbol
            self._state.last_refresh = datetime.now(timezone.utc)

    async def merge_quotes(self, quotes: list[QuoteSnapshot]) -> None:
        async with self._lock:
            for quote in quotes:
                self._state.quotes[quote.symbol] = replace(quote)
            self._state.last_refresh = datetime.now(timezone.utc)

    async def replace_orders(self, orders: list[OrderSnapshot]) -> None:
        async with self._lock:
            self._state.orders = [replace(order) for order in orders]
            self._state.last_refresh = datetime.now(timezone.utc)

    async def set_selection(
        self, panel: str, symbol: str | None = None
    ) -> None:
        async with self._lock:
            self._state.selected_panel = panel
            self._state.selected_symbol = symbol

    async def set_last_message(self, message: str | None) -> None:
        async with self._lock:
            self._state.last_message = message
            self._state.last_refresh = datetime.now(timezone.utc)
