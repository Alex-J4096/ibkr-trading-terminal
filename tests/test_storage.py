from __future__ import annotations

import sqlite3
from pathlib import Path

from ibkr_tui.storage.sqlite_store import SQLiteStore, TradeLogEntry


def test_sqlite_store_writes_trade_log(tmp_path: Path) -> None:
    db_path = tmp_path / "app.db"
    store = SQLiteStore(db_path)
    store.log_trade_event(
        TradeLogEntry(
            event_type="submit_order",
            status="submitted",
            message="Submitted order 1: BUY 1 AAPL MKT DAY",
            symbol="AAPL",
            side="BUY",
            order_type="MKT",
            quantity=1,
            order_id=1,
            account_mode="paper",
        )
    )
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT event_type, status, symbol, side, order_id, account_mode FROM trade_logs"
        ).fetchone()
    assert row == ("submit_order", "submitted", "AAPL", "BUY", 1, "paper")
