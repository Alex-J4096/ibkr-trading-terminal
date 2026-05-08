from __future__ import annotations

from ibkr_tui.config import Settings


def test_default_price_color_mode_is_red_down_green_up() -> None:
    settings = Settings()
    assert settings.ui.price_color_mode == "red_down_green_up"
