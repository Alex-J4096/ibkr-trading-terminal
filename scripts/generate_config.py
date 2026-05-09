from __future__ import annotations

import argparse
from pathlib import Path

from ibkr_tui.config import Settings


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate a starter config.toml for ibkr-tui."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("config.toml"),
        help="Path to write the generated TOML file.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite the output file if it already exists.",
    )
    return parser


def render_config(settings: Settings) -> str:
    watchlist = ", ".join(f'"{symbol}"' for symbol in settings.ui.watchlist)
    return "\n".join(
        [
            "# IBKR API connection settings.",
            "[ibkr]",
            "# IB Gateway / TWS host.",
            f'host = "{settings.ibkr.host}"',
            "# Common ports: 4002/7497 for Paper, 4001/7496 for Live.",
            f"port = {settings.ibkr.port}",
            "# Unique client ID for this application session.",
            f"client_id = {settings.ibkr.client_id}",
            "# Set to true to disable all order placement and cancellation.",
            f"readonly = {str(settings.ibkr.readonly).lower()}",
            "",
            "# Market data provider settings.",
            "[market_data]",
            "# Current supported provider.",
            f'provider = "{settings.market_data.provider}"',
            "# Finnhub API key.",
            'api_key = ""',
            "# Finnhub WebSocket endpoint.",
            f'websocket_url = "{settings.market_data.websocket_url}"',
            "",
            "# Trading behavior settings.",
            "[trading]",
            "# Default account mode label when auto-detection is unavailable.",
            f'account_mode = "{settings.trading.account_mode}"',
            "# Require typing CONFIRM before submitting orders in Live mode.",
            f"confirm_live_orders = {str(settings.trading.confirm_live_orders).lower()}",
            "# Allow market orders to be submitted.",
            f"allow_market_orders = {str(settings.trading.allow_market_orders).lower()}",
            "",
            "# Risk control settings.",
            "[risk]",
            "# Maximum notional value allowed per order in USD.",
            f"max_order_value_usd = {settings.risk.max_order_value_usd}",
            "# Maximum share quantity allowed per order.",
            f"max_order_qty = {settings.risk.max_order_qty}",
            "# Maximum number of orders allowed in a rolling 24-hour window.",
            f"max_daily_orders = {settings.risk.max_daily_orders}",
            "# Cooldown in seconds before the same symbol can be traded again.",
            f"cooldown_seconds = {settings.risk.cooldown_seconds}",
            "# Keep strong confirmation enabled for flatten-all actions.",
            "require_confirm_flatten_all = "
            f"{str(settings.risk.require_confirm_flatten_all).lower()}",
            "",
            "# UI and refresh settings.",
            "[ui]",
            "# UI refresh interval in milliseconds.",
            f"refresh_interval_ms = {settings.ui.refresh_interval_ms}",
            "# red_down_green_up or red_up_green_down.",
            f'price_color_mode = "{settings.ui.price_color_mode}"',
            "# Symbols shown in the watchlist panel.",
            f"watchlist = [{watchlist}]",
            "",
        ]
    )


def main() -> int:
    args = build_parser().parse_args()
    output_path = args.output.resolve()
    if output_path.exists() and not args.force:
        print(f"Refusing to overwrite existing file: {output_path}")
        print("Re-run with --force to overwrite it.")
        return 1

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_config(Settings()), encoding="utf-8")
    print(f"Generated config: {output_path}")
    print("Fill in [market_data].api_key and adjust IB host/port before running the app.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
