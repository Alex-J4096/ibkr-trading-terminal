from __future__ import annotations

import argparse
from pathlib import Path

from .app import IBKRTerminalApp
from .config import load_settings


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="IBKR TUI trading terminal")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config.toml"),
        help="Path to TOML configuration file.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    settings = load_settings(args.config)
    app = IBKRTerminalApp(settings)
    app.run()


if __name__ == "__main__":
    main()
