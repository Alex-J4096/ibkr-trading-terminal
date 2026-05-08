from __future__ import annotations

from ibkr_tui.config import load_settings


def test_load_settings_uses_env_for_finnhub_api_key(monkeypatch) -> None:
    monkeypatch.setenv("FINNHUB_API_KEY", "env-key")
    settings = load_settings("tests/nonexistent-config.toml")
    assert settings.market_data.api_key == "env-key"
