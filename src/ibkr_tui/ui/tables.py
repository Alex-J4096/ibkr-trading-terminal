from __future__ import annotations

from textual.widgets import DataTable


class PositionsTable(DataTable):
    def __init__(self) -> None:
        super().__init__(zebra_stripes=True, cursor_type="row")
        self.add_columns("Symbol", "Qty", "Last", "Avg Cost", "Mkt Value", "PnL", "PnL %")


class WatchlistTable(DataTable):
    def __init__(self) -> None:
        super().__init__(zebra_stripes=True, cursor_type="row")
        self.add_columns("Symbol", "Last", "Change", "Change %", "Status")


class OrdersTable(DataTable):
    def __init__(self) -> None:
        super().__init__(zebra_stripes=True, cursor_type="row")
        self.add_columns(
            "Order ID",
            "Symbol",
            "Side",
            "Type",
            "Qty",
            "Limit",
            "Status",
            "Filled",
            "Remaining",
        )
