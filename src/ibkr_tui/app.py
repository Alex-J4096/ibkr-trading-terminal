from __future__ import annotations

import asyncio

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual import work
from textual.widgets import Footer, Header, Static

from .broker.finnhub_client import FinnhubMarketDataClient
from .broker.ib_client import IBGatewayClient, RefreshController
from .config import Settings
from .models import AppStateSnapshot
from .order_service import OrderService
from .risk import RiskManager
from .state import AppStateStore
from .ui.command_palette import TerminalCommandProvider
from .ui.screens import ConfirmModal, InfoModal, OrderTicketModal
from .ui.tables import OrdersTable, PositionsTable, WatchlistTable
from .ui.widgets import AccountSummaryWidget, StatusBar


class IBKRTerminalApp(App[None]):
    CSS = """
    Screen {
        layout: vertical;
        background: #091017;
        color: #d7e3f4;
    }
    #main-grid {
        height: 1fr;
        padding: 1 2;
    }
    #top-row {
        height: 1fr;
    }
    #positions-panel {
        width: 2fr;
    }
    #account-panel {
        width: 1fr;
    }
    #bottom-row {
        height: 18;
    }
    .panel {
        border: round #29526d;
        padding: 0 1;
        margin-bottom: 1;
    }
    .panel-title {
        color: #8fd3ff;
        text-style: bold;
        margin-bottom: 1;
    }
    DataTable {
        height: 1fr;
        background: #091017;
    }
    #status-bar {
        dock: bottom;
        height: 3;
        padding: 0 2;
        background: #112131;
        color: #d7e3f4;
    }
    #modal-body {
        width: 64;
        padding: 1 2;
        border: round #29526d;
        background: #112131;
    }
    #modal-title {
        color: #8fd3ff;
        text-style: bold;
        margin-bottom: 1;
    }
    #modal-message {
        margin-bottom: 1;
    }
    #account-summary {
        content-align: left top;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh", "Refresh"),
        Binding("tab", "cycle_panel", "Next Panel"),
        Binding("enter", "view_selection", "View"),
        Binding("b", "buy", "Buy"),
        Binding("s", "sell", "Sell"),
        Binding("x", "flatten", "Flatten"),
        Binding("c", "cancel_order", "Cancel"),
        Binding("/", "command_palette", "Command"),
    ]

    COMMANDS = {TerminalCommandProvider}

    def __init__(self, settings: Settings) -> None:
        super().__init__()
        self.settings = settings
        self.state = AppStateStore()
        self.ib_client = IBGatewayClient(settings)
        self.risk_manager = RiskManager(settings)
        self.order_service = OrderService(self.ib_client, self.risk_manager, self.state)
        self.refresh_controller = RefreshController(
            self.ib_client,
            FinnhubMarketDataClient(settings),
            self.state,
            settings.ui.watchlist,
        )
        self._refresh_task: asyncio.Task[None] | None = None
        self._refresh_interval = max(0.2, settings.ui.refresh_interval_ms / 1000)
        self._position_symbols: list[str] = []
        self._watchlist_symbols: list[str] = list(settings.ui.watchlist)
        self._order_ids: list[int] = []
        self._last_snapshot = AppStateSnapshot()

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Container(id="main-grid"):
            with Horizontal(id="top-row"):
                with Vertical(id="positions-panel", classes="panel"):
                    yield Static("Positions", classes="panel-title")
                    yield PositionsTable()
                with Vertical(id="account-panel", classes="panel"):
                    yield Static("Account Summary", classes="panel-title")
                    yield AccountSummaryWidget(id="account-summary")
            with Horizontal(id="bottom-row"):
                with Vertical(classes="panel"):
                    yield Static("Watchlist", classes="panel-title")
                    yield WatchlistTable()
                with Vertical(classes="panel"):
                    yield Static("Orders", classes="panel-title")
                    yield OrdersTable()
        yield StatusBar(id="status-bar")
        yield Footer()

    async def on_mount(self) -> None:
        await self.refresh_controller.start()
        await self._run_refresh()
        self.query_one(PositionsTable).focus()
        self.set_interval(self._refresh_interval, self._queue_refresh)

    async def on_unmount(self) -> None:
        if self._refresh_task is not None:
            self._refresh_task.cancel()
        await self.refresh_controller.shutdown()

    async def action_refresh(self) -> None:
        await self._run_refresh()

    def action_cycle_panel(self) -> None:
        tables = [
            self.query_one(PositionsTable),
            self.query_one(WatchlistTable),
            self.query_one(OrdersTable),
        ]
        current_index = next((index for index, table in enumerate(tables) if table.has_focus), -1)
        tables[(current_index + 1) % len(tables)].focus()

    def action_view_selection(self) -> None:
        self._show_selection_details()

    def action_buy(self) -> None:
        self._action_buy()

    @work(exclusive=True, group="trading", exit_on_error=False)
    async def _action_buy(self) -> None:
        symbol = self._selected_symbol()
        if symbol is None:
            self.push_screen(InfoModal("No symbol selected"))
            return
        request = await self.push_screen_wait(OrderTicketModal(symbol, "BUY", self.state))
        if request is None:
            return
        await self._confirm_and_submit(request)

    def action_sell(self) -> None:
        self._action_sell()

    @work(exclusive=True, group="trading", exit_on_error=False)
    async def _action_sell(self) -> None:
        symbol = self._selected_symbol()
        if symbol is None:
            self.push_screen(InfoModal("No symbol selected"))
            return
        request = await self.push_screen_wait(OrderTicketModal(symbol, "SELL", self.state))
        if request is None:
            return
        await self._confirm_and_submit(request)

    def action_flatten(self) -> None:
        self._action_flatten()

    @work(exclusive=True, group="trading", exit_on_error=False)
    async def _action_flatten(self) -> None:
        symbol = self._selected_position_symbol()
        if symbol is None:
            self.push_screen(InfoModal("Select a position to flatten"))
            return
        position = (await self.state.snapshot()).positions[symbol]
        confirmed = await self.push_screen_wait(
            ConfirmModal(
                f"Flatten {symbol}: {'SELL' if position.quantity > 0 else 'BUY'} {abs(position.quantity):g} at market?"
            )
        )
        if not confirmed:
            return
        await self._run_trade_action(lambda: self.order_service.flatten_position(symbol))

    def action_cancel_order(self) -> None:
        self._action_cancel_order()

    @work(exclusive=True, group="trading", exit_on_error=False)
    async def _action_cancel_order(self) -> None:
        order_id = self._selected_order_id()
        if order_id is None:
            self.push_screen(InfoModal("Select an open order to cancel"))
            return
        confirmed = await self.push_screen_wait(
            ConfirmModal(f"Cancel order {order_id}?")
        )
        if not confirmed:
            return
        await self._run_trade_action(lambda: self.order_service.cancel_order(order_id))

    def _queue_refresh(self) -> None:
        if self._refresh_task is None or self._refresh_task.done():
            self._refresh_task = asyncio.create_task(self._run_refresh())

    async def _run_refresh(self) -> None:
        await self.refresh_controller.refresh()
        snapshot = await self.state.snapshot()
        self._render_state(snapshot)

    def _render_state(self, snapshot: AppStateSnapshot) -> None:
        self._last_snapshot = snapshot
        self._render_positions(snapshot)
        self._render_account_summary(snapshot)
        self._render_watchlist(snapshot)
        self._render_orders(snapshot)
        self._render_status(snapshot)

    def _render_positions(self, snapshot: AppStateSnapshot) -> None:
        table = self.query_one(PositionsTable)
        cursor_row = table.cursor_row
        table.clear()
        self._position_symbols = list(snapshot.positions.keys())
        if not snapshot.positions:
            table.add_row("-", "-", "-", "-", "-", "No positions", "-")
            table.cursor_type = "row"
            self._restore_cursor(table, cursor_row, 1)
            return
        for position in snapshot.positions.values():
            table.add_row(
                position.symbol,
                self._fmt_number(position.quantity, 0),
                self._fmt_number(position.last_price),
                self._fmt_number(position.average_cost),
                self._fmt_number(position.market_value),
                self._fmt_signed(position.unrealized_pnl, colorize=True),
                self._fmt_percent(position.pnl_percent, colorize=True),
            )
        self._restore_cursor(table, cursor_row, len(self._position_symbols))

    def _render_account_summary(self, snapshot: AppStateSnapshot) -> None:
        summary = snapshot.account_summary
        lines = [
            f"Account: {summary.account_id or '-'}",
            f"Currency: {summary.currency or '-'}",
            "",
            f"Net Liq: {self._fmt_number(summary.net_liquidation)}",
            f"Available: {self._fmt_number(summary.available_funds)}",
            f"Buying Power: {self._fmt_number(summary.buying_power)}",
            f"Cash: {self._fmt_number(summary.cash_value)}",
            "",
            f"Positions: {len(snapshot.positions)}",
            f"Open Orders: {len(snapshot.orders)}",
        ]
        self.query_one(AccountSummaryWidget).update("\n".join(lines))

    def _render_watchlist(self, snapshot: AppStateSnapshot) -> None:
        table = self.query_one(WatchlistTable)
        cursor_row = table.cursor_row
        table.clear()
        for symbol in self.settings.ui.watchlist:
            quote = snapshot.quotes.get(symbol)
            if quote is None:
                table.add_row(symbol, "-", "-", "-", "UNSUBSCRIBED")
                continue
            table.add_row(
                symbol,
                self._fmt_number(quote.last_price),
                self._fmt_signed(quote.change, colorize=True),
                self._fmt_percent(quote.change_percent, colorize=True),
                quote.data_status,
            )
        self._restore_cursor(table, cursor_row, len(self._watchlist_symbols))

    def _render_orders(self, snapshot: AppStateSnapshot) -> None:
        table = self.query_one(OrdersTable)
        cursor_row = table.cursor_row
        table.clear()
        self._order_ids = [order.order_id for order in snapshot.orders]
        if not snapshot.orders:
            table.add_row("-", "-", "-", "-", "-", "-", "No open orders", "-", "-")
            self._restore_cursor(table, cursor_row, 1)
            return
        for order in snapshot.orders:
            table.add_row(
                str(order.order_id),
                order.symbol,
                order.side,
                order.order_type,
                self._fmt_number(order.quantity, 0),
                self._fmt_number(order.limit_price),
                order.status,
                self._fmt_number(order.filled, 0),
                self._fmt_number(order.remaining, 0),
            )
        self._restore_cursor(table, cursor_row, len(self._order_ids))

    def _render_status(self, snapshot: AppStateSnapshot) -> None:
        status_bar = self.query_one(StatusBar)
        account_id = snapshot.account_summary.account_id or "-"
        mode = self.settings.trading.account_mode.upper()
        selected = self._selected_symbol() or "-"
        refreshed = (
            snapshot.last_refresh.astimezone().strftime("%H:%M:%S")
            if snapshot.last_refresh
            else "-"
        )
        message = f" | Message: {snapshot.last_message}" if snapshot.last_message else ""
        error = f" | Error: {snapshot.last_error}" if snapshot.last_error else ""
        status_bar.update(
            " | ".join(
                [
                    f"IB: {snapshot.connection_status.upper()}",
                    f"Quotes: {snapshot.market_data_status.upper()}",
                    f"Account: {account_id}",
                    f"Mode: {mode}",
                    f"Selected: {selected}",
                    f"Last Refresh: {refreshed}",
                ]
            )
            + message
            + error
        )

    def _show_selection_details(self) -> None:
        if self.query_one(OrdersTable).has_focus:
            order_id = self._selected_order_id()
            order = next(
                (item for item in self._last_snapshot.orders if item.order_id == order_id),
                None,
            )
            if order is None:
                self.push_screen(InfoModal("No order selected"))
                return
            message = "\n".join(
                [
                    f"Order {order.order_id} | {order.symbol}",
                    f"Side: {order.side}",
                    f"Type: {order.order_type}",
                    f"TIF: {order.tif}",
                    f"Outside RTH: {'Yes' if order.outside_rth else 'No'}",
                    f"Qty: {self._fmt_number(order.quantity, 0)}",
                    f"Limit: {self._fmt_number(order.limit_price)}",
                    f"Status: {order.status}",
                    f"Filled: {self._fmt_number(order.filled, 0)}",
                    f"Remaining: {self._fmt_number(order.remaining, 0)}",
                    f"Avg Fill: {self._fmt_number(order.avg_fill_price)}",
                    f"Account: {order.account_id or '-'}",
                ]
            )
            self.push_screen(InfoModal(message))
            return

        symbol = self._selected_symbol()
        if symbol is None:
            self.push_screen(InfoModal("No symbol selected"))
            return

        position = self._last_snapshot.positions.get(symbol)
        quote = self._last_snapshot.quotes.get(symbol)
        lines = [f"Symbol: {symbol}"]
        if position is not None:
            lines.extend(
                [
                    f"Qty: {self._fmt_number(position.quantity, 0)}",
                    f"Avg Cost: {self._fmt_number(position.average_cost)}",
                    f"Market Value: {self._fmt_number(position.market_value)}",
                    f"PnL: {self._fmt_signed_text(position.unrealized_pnl)}",
                    f"PnL %: {self._fmt_percent_text(position.pnl_percent)}",
                    f"Currency: {position.currency}",
                ]
            )
        else:
            lines.append("Qty: Not currently held")

        if quote is not None:
            lines.extend(
                [
                    "",
                    f"Last: {self._fmt_number(quote.last_price)}",
                    f"Bid: {self._fmt_number(quote.bid)}",
                    f"Ask: {self._fmt_number(quote.ask)}",
                    f"Change: {self._fmt_signed_text(quote.change)}",
                    f"Change %: {self._fmt_percent_text(quote.change_percent)}",
                    f"Status: {quote.data_status}",
                ]
            )
        self.push_screen(InfoModal("\n".join(lines)))

    @staticmethod
    def _restore_cursor(table, previous_row: int, row_count: int) -> None:
        if row_count <= 0:
            return
        target = max(0, min(row_count - 1, previous_row))
        table.move_cursor(row=target)

    async def _confirm_and_submit(self, request) -> None:
        confirmation = (
            f"{request.side} {request.quantity:g} {request.symbol} {request.order_type} {request.tif}"
        )
        if request.outside_rth:
            confirmation += " outsideRth"
        if request.limit_price is not None:
            confirmation += f" @ {request.limit_price:,.2f}"
        confirmed = await self.push_screen_wait(ConfirmModal(f"Submit {confirmation}?"))
        if not confirmed:
            return
        await self._run_trade_action(lambda: self.order_service.submit_order(request))

    async def _run_trade_action(self, action) -> None:
        try:
            message = await action()
            await self.state.set_last_message(message)
            self.notify(message)
            await self._run_refresh()
        except Exception as exc:
            snapshot = await self.state.snapshot()
            await self.state.update_connection(
                snapshot.connection_status,
                snapshot.connection_detail,
                str(exc),
            )
            self.notify(str(exc), severity="error")
            snapshot = await self.state.snapshot()
            self._render_state(snapshot)

    def _selected_symbol(self) -> str | None:
        if self.query_one(PositionsTable).has_focus:
            return self._selected_position_symbol()
        if self.query_one(WatchlistTable).has_focus:
            index = self.query_one(WatchlistTable).cursor_row
            if 0 <= index < len(self._watchlist_symbols):
                return self._watchlist_symbols[index]
        return self._selected_position_symbol() or (
            self._watchlist_symbols[0] if self._watchlist_symbols else None
        )

    def _selected_position_symbol(self) -> str | None:
        table = self.query_one(PositionsTable)
        index = table.cursor_row
        if 0 <= index < len(self._position_symbols):
            return self._position_symbols[index]
        return None

    def _selected_order_id(self) -> int | None:
        table = self.query_one(OrdersTable)
        if not table.has_focus:
            return None
        index = table.cursor_row
        if 0 <= index < len(self._order_ids):
            return self._order_ids[index]
        return None

    @staticmethod
    def _fmt_number(value: float | None, digits: int = 2) -> str:
        if value is None:
            return "-"
        return f"{value:,.{digits}f}"

    def _fmt_signed(self, value: float | None, colorize: bool = False) -> str | Text:
        if value is None:
            return "-"
        rendered = f"{value:+,.2f}"
        if not colorize:
            return rendered
        return Text(rendered, style=self._value_style(value))

    def _fmt_percent(self, value: float | None, colorize: bool = False) -> str | Text:
        if value is None:
            return "-"
        rendered = f"{value:+.2f}%"
        if not colorize:
            return rendered
        return Text(rendered, style=self._value_style(value))

    @staticmethod
    def _fmt_percent_text(value: float | None) -> str:
        if value is None:
            return "-"
        return f"{value:+.2f}%"

    @staticmethod
    def _fmt_signed_text(value: float | None) -> str:
        if value is None:
            return "-"
        return f"{value:+,.2f}"

    def _value_style(self, value: float) -> str:
        if value == 0:
            return "#d7e3f4"
        if self.settings.ui.price_color_mode == "red_up_green_down":
            return "#ff5f5f" if value > 0 else "#32cd7a"
        return "#32cd7a" if value > 0 else "#ff5f5f"
