from __future__ import annotations

from ibkr_tui.config import Settings
from ibkr_tui.models import AppStateSnapshot, PositionSnapshot, QuoteSnapshot
from ibkr_tui.risk import RiskManager


def make_settings(*, readonly: bool = False) -> Settings:
    settings = Settings()
    settings.ibkr.readonly = readonly
    settings.risk.max_order_qty = 100
    settings.risk.max_order_value_usd = 5000
    settings.risk.max_daily_orders = 2
    settings.risk.cooldown_seconds = 3
    return settings


def make_snapshot() -> AppStateSnapshot:
    snapshot = AppStateSnapshot(
        connection_status="connected",
        market_data_status="connected",
    )
    snapshot.quotes["AAPL"] = QuoteSnapshot(symbol="AAPL", last_price=100)
    snapshot.positions["AAPL"] = PositionSnapshot(
        symbol="AAPL",
        quantity=10,
        average_cost=90,
    )
    return snapshot


def test_risk_manager_rejects_readonly_mode() -> None:
    result = RiskManager(make_settings(readonly=True)).validate_order(
        make_snapshot(),
        symbol="AAPL",
        side="BUY",
        quantity=1,
        order_type="MKT",
    )
    assert not result.ok
    assert "readonly" in result.message


def test_risk_manager_rejects_large_notional() -> None:
    result = RiskManager(make_settings()).validate_order(
        make_snapshot(),
        symbol="AAPL",
        side="BUY",
        quantity=60,
        order_type="MKT",
    )
    assert not result.ok
    assert "max_order_value_usd" in result.message


def test_risk_manager_enforces_cooldown() -> None:
    manager = RiskManager(make_settings())
    snapshot = make_snapshot()
    first = manager.validate_order(
        snapshot,
        symbol="AAPL",
        side="BUY",
        quantity=1,
        order_type="MKT",
    )
    assert first.ok
    manager.record_order("AAPL")
    second = manager.validate_order(
        snapshot,
        symbol="AAPL",
        side="BUY",
        quantity=1,
        order_type="MKT",
    )
    assert not second.ok
    assert "cooldown" in second.message


def test_risk_manager_validates_flatten_position() -> None:
    result = RiskManager(make_settings()).validate_flatten(make_snapshot(), symbol="AAPL")
    assert result.ok


def test_risk_manager_detects_live_mode_from_port() -> None:
    settings = make_settings()
    settings.ibkr.port = 4001
    manager = RiskManager(settings)
    assert manager.effective_account_mode() == "live"
    assert manager.requires_live_confirmation()
