from __future__ import annotations

import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(slots=True)
class TradeLogEntry:
    event_type: str
    status: str
    message: str
    symbol: str | None = None
    side: str | None = None
    order_type: str | None = None
    quantity: float | None = None
    limit_price: float | None = None
    order_id: int | None = None
    account_mode: str | None = None
    created_at: datetime | None = None


class SQLiteStore:
    def __init__(self, path: str | Path = "data/app.db") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def log_trade_event(self, entry: TradeLogEntry) -> None:
        created_at = entry.created_at or datetime.now(timezone.utc)
        payload = asdict(entry)
        payload["created_at"] = created_at.isoformat()
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                """
                INSERT INTO trade_logs (
                    created_at,
                    event_type,
                    status,
                    message,
                    symbol,
                    side,
                    order_type,
                    quantity,
                    limit_price,
                    order_id,
                    account_mode
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload["created_at"],
                    payload["event_type"],
                    payload["status"],
                    payload["message"],
                    payload["symbol"],
                    payload["side"],
                    payload["order_type"],
                    payload["quantity"],
                    payload["limit_price"],
                    payload["order_id"],
                    payload["account_mode"],
                ),
            )
            conn.commit()

    def _init_db(self) -> None:
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS trade_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    message TEXT NOT NULL,
                    symbol TEXT,
                    side TEXT,
                    order_type TEXT,
                    quantity REAL,
                    limit_price REAL,
                    order_id INTEGER,
                    account_mode TEXT
                )
                """
            )
            conn.commit()
