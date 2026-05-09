from __future__ import annotations

import asyncio

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Input, Label, Static

from ..models import QuoteSnapshot
from ..order_service import OrderRequest
from ..state import AppStateStore


class InfoModal(ModalScreen[None]):
    def __init__(self, message: str) -> None:
        super().__init__()
        self.message = message

    def compose(self) -> ComposeResult:
        with Vertical(id="modal-body"):
            yield Static(self.message, id="modal-message")
            yield Button("Close", id="close")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "close":
            self.dismiss(None)


class ConfirmModal(ModalScreen[bool]):
    def __init__(self, message: str) -> None:
        super().__init__()
        self.message = message

    def compose(self) -> ComposeResult:
        with Vertical(id="modal-body"):
            yield Static(self.message, id="modal-message")
            yield Button("Confirm", variant="error", id="confirm")
            yield Button("Cancel", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "confirm")


class ConfirmTextModal(ModalScreen[bool]):
    def __init__(self, message: str, *, confirm_text: str = "CONFIRM") -> None:
        super().__init__()
        self.message = message
        self.confirm_text = confirm_text

    def compose(self) -> ComposeResult:
        with Vertical(id="modal-body"):
            yield Static(self.message, id="modal-message")
            yield Input(placeholder=self.confirm_text, id="confirm-text")
            yield Button("Confirm", variant="error", id="confirm")
            yield Button("Cancel", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.dismiss(False)
            return
        if event.button.id != "confirm":
            return
        typed = self.query_one("#confirm-text", Input).value.strip().upper()
        if typed != self.confirm_text.upper():
            self.app.notify(
                f"Type {self.confirm_text} to confirm",
                severity="error",
            )
            return
        self.dismiss(True)


class OrderTicketModal(ModalScreen[OrderRequest | None]):
    def __init__(self, symbol: str, side: str, state: AppStateStore) -> None:
        super().__init__()
        self.symbol = symbol
        self.side = side
        self.state = state

    def compose(self) -> ComposeResult:
        with Vertical(id="modal-body"):
            yield Label(f"{self.side} {self.symbol}", id="modal-title")
            yield Static("Last: - | Bid: - | Ask: - | Change: -", id="quote-summary")
            yield Label("Order Type: MKT or LMT")
            yield Input(value="MKT", id="order-type")
            yield Label("Quantity")
            yield Input(value="1", id="quantity")
            yield Label("Limit Price (required for LMT)")
            yield Input(placeholder="Optional", id="limit-price")
            yield Checkbox(
                "Allow pre/post market execution (outsideRth)",
                value=False,
                id="outside-rth",
            )
            yield Button("Submit", variant="primary", id="submit")
            yield Button("Cancel", id="cancel")

    def on_mount(self) -> None:
        self._queue_quote_refresh()
        self.set_interval(0.5, self._queue_quote_refresh)

    def _queue_quote_refresh(self) -> None:
        asyncio.create_task(self._refresh_quote_summary())

    async def _refresh_quote_summary(self) -> None:
        snapshot = await self.state.snapshot()
        quote = snapshot.quotes.get(self.symbol)
        self.query_one("#quote-summary", Static).update(self._render_quote_summary(quote))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.dismiss(None)
            return
        if event.button.id != "submit":
            return

        order_type = self.query_one("#order-type", Input).value.strip().upper() or "MKT"
        quantity_text = self.query_one("#quantity", Input).value.strip()
        limit_text = self.query_one("#limit-price", Input).value.strip()
        try:
            quantity = float(quantity_text)
        except ValueError:
            self.app.notify("Quantity must be a number", severity="error")
            return

        limit_price = None
        if limit_text:
            try:
                limit_price = float(limit_text)
            except ValueError:
                self.app.notify("Limit price must be a number", severity="error")
                return
        if order_type == "LMT" and limit_price is None:
            self.app.notify("Limit order requires limit price", severity="error")
            return
        if order_type not in {"MKT", "LMT"}:
            self.app.notify("Order type must be MKT or LMT", severity="error")
            return
        outside_rth = self.query_one("#outside-rth", Checkbox).value

        self.dismiss(
            OrderRequest(
                symbol=self.symbol,
                side=self.side,
                quantity=quantity,
                order_type=order_type,
                tif="DAY",
                outside_rth=outside_rth,
                limit_price=limit_price,
            )
        )

    @staticmethod
    def _render_quote_summary(quote: QuoteSnapshot | None) -> str:
        if quote is None:
            return "Last: - | Bid: - | Ask: - | Change: -"
        last_price = "-" if quote.last_price is None else f"{quote.last_price:,.2f}"
        bid = "-" if quote.bid is None else f"{quote.bid:,.2f}"
        ask = "-" if quote.ask is None else f"{quote.ask:,.2f}"
        change = "-" if quote.change_percent is None else f"{quote.change_percent:+.2f}%"
        return f"Last: {last_price} | Bid: {bid} | Ask: {ask} | Change: {change}"
