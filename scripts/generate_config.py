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
            "[ibkr]",
            f'host = "{settings.ibkr.host}"',
            f"port = {settings.ibkr.port}",
            f"client_id = {settings.ibkr.client_id}",
            f"readonly = {str(settings.ibkr.readonly).lower()}",
            "",
            "[market_data]",
            f'provider = "{settings.market_data.provider}"',
            'api_key = ""',
            f'websocket_url = "{settings.market_data.websocket_url}"',
            "",
            "[trading]",
            f'account_mode = "{settings.trading.account_mode}"',
            f"confirm_live_orders = {str(settings.trading.confirm_live_orders).lower()}",
            f"allow_market_orders = {str(settings.trading.allow_market_orders).lower()}",
            "",
            "[risk]",
            f"max_order_value_usd = {settings.risk.max_order_value_usd}",
            f"max_order_qty = {settings.risk.max_order_qty}",
            f"max_daily_orders = {settings.risk.max_daily_orders}",
            f"cooldown_seconds = {settings.risk.cooldown_seconds}",
            "require_confirm_flatten_all = "
            f"{str(settings.risk.require_confirm_flatten_all).lower()}",
            "",
            "[ui]",
            f"refresh_interval_ms = {settings.ui.refresh_interval_ms}",
            f'price_color_mode = "{settings.ui.price_color_mode}"',
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
