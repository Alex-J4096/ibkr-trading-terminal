from __future__ import annotations

from ibkr_tui.broker.market_data import quote_from_finnhub_rest, quote_from_finnhub_trade


def test_quote_from_finnhub_rest_builds_change_fields() -> None:
    quote = quote_from_finnhub_rest("AAPL", {"c": 210.0, "pc": 200.0})
    assert quote.symbol == "AAPL"
    assert quote.last_price == 210.0
    assert quote.previous_close == 200.0
    assert quote.change == 10.0
    assert quote.change_percent == 5.0
    assert quote.data_status == "REST"


def test_quote_from_finnhub_trade_preserves_previous_close() -> None:
    previous = quote_from_finnhub_rest("AAPL", {"c": 210.0, "pc": 200.0})
    quote = quote_from_finnhub_trade("AAPL", {"p": 212.5, "t": 1710000000000}, previous)
    assert quote.symbol == "AAPL"
    assert quote.last_price == 212.5
    assert quote.previous_close == 200.0
    assert quote.change == 12.5
    assert quote.change_percent == 6.25
    assert quote.data_status == "STREAMING"
