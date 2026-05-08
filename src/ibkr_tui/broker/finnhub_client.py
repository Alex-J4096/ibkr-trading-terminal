from __future__ import annotations

import asyncio
import json
from contextlib import suppress

import finnhub
from websockets import connect
from websockets.exceptions import ConnectionClosed

from ..config import Settings
from ..models import QuoteSnapshot
from ..state import AppStateStore
from .market_data import quote_from_finnhub_rest, quote_from_finnhub_trade


class FinnhubMarketDataClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._rest_client = (
            finnhub.Client(api_key=settings.market_data.api_key)
            if settings.market_data.api_key
            else None
        )
        self._symbols: set[str] = set()
        self._quotes: dict[str, QuoteSnapshot] = {}
        self._task: asyncio.Task[None] | None = None
        self._send_lock = asyncio.Lock()
        self._socket = None
        self._state: AppStateStore | None = None

    async def start(self, state: AppStateStore, symbols: list[str]) -> None:
        self._state = state
        await self.ensure_symbols(symbols)
        if not self.settings.market_data.api_key:
            await state.update_market_data_status(
                "error",
                "Finnhub API key missing",
                "Set FINNHUB_API_KEY or [market_data].api_key in config.toml",
            )
            return
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._run())

    async def ensure_symbols(self, symbols: list[str]) -> None:
        new_symbols = {symbol.upper() for symbol in symbols if symbol}
        if not new_symbols:
            return
        added = sorted(new_symbols - self._symbols)
        self._symbols.update(new_symbols)
        if self._rest_client and added:
            await self.refresh_reference_quotes(added)
        if self._socket is not None:
            async with self._send_lock:
                for symbol in added:
                    await self._socket.send(
                        json.dumps({"type": "subscribe", "symbol": symbol})
                    )

    async def refresh_reference_quotes(self, symbols: list[str]) -> None:
        if not self._rest_client or not self._state:
            return
        quotes: list[QuoteSnapshot] = []
        for symbol in symbols:
            payload = await asyncio.to_thread(self._rest_client.quote, symbol)
            existing = self._quotes.get(symbol)
            quote = quote_from_finnhub_rest(symbol, payload)
            if existing and existing.last_price is not None:
                quote.last_price = existing.last_price
                quote.change = (
                    quote.last_price - quote.previous_close
                    if quote.previous_close not in (None, 0)
                    else None
                )
                quote.change_percent = (
                    (quote.change / quote.previous_close) * 100
                    if quote.change is not None and quote.previous_close not in (None, 0)
                    else None
                )
                quote.data_status = existing.data_status
                quote.updated_at = existing.updated_at
            self._quotes[symbol] = quote
            quotes.append(quote)
        await self._state.merge_quotes(quotes)

    async def shutdown(self) -> None:
        if self._task is not None:
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task

    async def _run(self) -> None:
        assert self._state is not None
        while True:
            try:
                await self._state.update_market_data_status(
                    "connecting", "Connecting to Finnhub WebSocket"
                )
                async with connect(
                    f"{self.settings.market_data.websocket_url}?token={self.settings.market_data.api_key}"
                ) as websocket:
                    self._socket = websocket
                    async with self._send_lock:
                        for symbol in sorted(self._symbols):
                            await websocket.send(
                                json.dumps({"type": "subscribe", "symbol": symbol})
                            )
                    await self._state.update_market_data_status(
                        "connected", "Finnhub streaming connected"
                    )
                    async for raw_message in websocket:
                        await self._handle_message(raw_message)
            except asyncio.CancelledError:
                raise
            except ConnectionClosed as exc:
                await self._state.update_market_data_status(
                    "disconnected", "Finnhub socket closed", str(exc)
                )
                await asyncio.sleep(2)
            except Exception as exc:
                await self._state.update_market_data_status(
                    "error", "Finnhub streaming failed", str(exc)
                )
                await asyncio.sleep(2)
            finally:
                self._socket = None

    async def _handle_message(self, raw_message: str) -> None:
        assert self._state is not None
        payload = json.loads(raw_message)
        if payload.get("type") != "trade":
            return
        updates: list[QuoteSnapshot] = []
        for trade in payload.get("data", []):
            symbol = str(trade.get("s", "")).upper()
            if not symbol:
                continue
            quote = quote_from_finnhub_trade(symbol, trade, self._quotes.get(symbol))
            self._quotes[symbol] = quote
            updates.append(quote)
        if updates:
            await self._state.merge_quotes(updates)
