from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static

from ..order_service import OrderRequest


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


class OrderTicketModal(ModalScreen[OrderRequest | None]):
    def __init__(self, symbol: str, side: str) -> None:
        super().__init__()
        self.symbol = symbol
        self.side = side

    def compose(self) -> ComposeResult:
        with Vertical(id="modal-body"):
            yield Label(f"{self.side} {self.symbol}", id="modal-title")
            yield Label("Order Type: MKT or LMT")
            yield Input(value="MKT", id="order-type")
            yield Label("Quantity")
            yield Input(value="1", id="quantity")
            yield Label("Limit Price (required for LMT)")
            yield Input(placeholder="Optional", id="limit-price")
            yield Button("Submit", variant="primary", id="submit")
            yield Button("Cancel", id="cancel")

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

        self.dismiss(
            OrderRequest(
                symbol=self.symbol,
                side=self.side,
                quantity=quantity,
                order_type=order_type,
                limit_price=limit_price,
            )
        )
