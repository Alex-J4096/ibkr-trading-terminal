from __future__ import annotations

import sqlite3
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def test_init_db_script_creates_trade_log_table(tmp_path: Path) -> None:
    db_path = tmp_path / "app.db"
    script_path = ROOT / "scripts" / "init_db.py"
    result = subprocess.run(
        [sys.executable, str(script_path), "--path", str(db_path)],
        capture_output=True,
        text=True,
        check=False,
        cwd=ROOT,
    )
    assert result.returncode == 0
    assert "Initialized database" in result.stdout
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='trade_logs'"
        ).fetchone()
    assert row == ("trade_logs",)
