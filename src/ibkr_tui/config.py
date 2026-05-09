from __future__ import annotations

import os
from pathlib import Path
import tomllib
from typing import Literal

from pydantic import BaseModel, Field


class IBKRConfig(BaseModel):
    host: str = "127.0.0.1"
    port: int = 7497
    client_id: int = 7
    readonly: bool = True


class MarketDataConfig(BaseModel):
    provider: Literal["finnhub"] = "finnhub"
    api_key: str = ""
    websocket_url: str = "wss://ws.finnhub.io"


class TradingConfig(BaseModel):
    account_mode: Literal["paper", "live"] = "paper"
    confirm_live_orders: bool = True
    allow_market_orders: bool = True


class RiskConfig(BaseModel):
    max_order_value_usd: float = 5000
    max_order_qty: int = 100
    max_daily_orders: int = 20
    cooldown_seconds: int = 3
    require_confirm_flatten_all: bool = True


class UIConfig(BaseModel):
    refresh_interval_ms: int = 1000
    price_color_mode: Literal[
        "red_down_green_up", "red_up_green_down"
    ] = "red_down_green_up"
    watchlist: list[str] = Field(
        default_factory=lambda: ["NVDA", "AAPL", "TSM", "AMD", "MSFT"]
    )


class Settings(BaseModel):
    ibkr: IBKRConfig = Field(default_factory=IBKRConfig)
    market_data: MarketDataConfig = Field(default_factory=MarketDataConfig)
    trading: TradingConfig = Field(default_factory=TradingConfig)
    risk: RiskConfig = Field(default_factory=RiskConfig)
    ui: UIConfig = Field(default_factory=UIConfig)


def infer_account_mode(settings: Settings) -> Literal["paper", "live"]:
    if settings.ibkr.port in {4001, 7496}:
        return "live"
    if settings.ibkr.port in {4002, 7497}:
        return "paper"
    return settings.trading.account_mode


def load_settings(path: str | Path | None = None) -> Settings:
    config_path = Path(path) if path is not None else Path("config.toml")
    if not config_path.exists():
        settings = Settings()
    else:
        with config_path.open("rb") as handle:
            data = tomllib.load(handle)
        settings = Settings.model_validate(data)

    if not settings.market_data.api_key:
        settings.market_data.api_key = os.environ.get("FINNHUB_API_KEY", "")
    return settings
