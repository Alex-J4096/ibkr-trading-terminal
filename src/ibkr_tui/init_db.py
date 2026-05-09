from __future__ import annotations

import argparse
from pathlib import Path
import sqlite3

from .storage.sqlite_store import SQLiteStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Initialize the local SQLite database for ibkr-tui."
    )
    parser.add_argument(
        "--path",
        type=Path,
        default=Path("data/app.db"),
        help="Path to the SQLite database file.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Delete the existing database file before initializing it.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    db_path = args.path.resolve()
    if db_path.exists() and not args.force:
        try:
            with sqlite3.connect(db_path) as conn:
                conn.execute("SELECT 1 FROM trade_logs LIMIT 1")
            print(f"Database already initialized: {db_path}")
            print("Re-run with --force to recreate it.")
            return 0
        except sqlite3.Error:
            print(f"Existing file is not a compatible database: {db_path}")
            print("Re-run with --force to recreate it.")
            return 1

    if db_path.exists() and args.force:
        db_path.unlink()

    SQLiteStore(db_path)
    print(f"Initialized database: {db_path}")
    print("Created table: trade_logs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
