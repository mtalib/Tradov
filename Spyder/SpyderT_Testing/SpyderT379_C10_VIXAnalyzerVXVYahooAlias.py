"""Regression for C10 VXV Yahoo symbol drift.

Yahoo's legacy ``^VXV`` symbol stopped returning quote data. Spyder should keep
publishing internal ``VXV`` metrics, but source them from Yahoo's live
``^VIX3M`` ticker.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from Spyder.SpyderC_MarketData import SpyderC10_VIXAnalyzer as c10


def test_update_realtime_data_uses_vix3m_symbol_for_vxv(monkeypatch) -> None:
    symbols_requested: list[str] = []
    prices = {
        "^VIX": 18.04,
        "^VIX9D": 16.86,
        "^VVIX": 91.18,
        "^VIX3M": 20.92,
        "^VXMT": 16.32,
    }

    class _Ticker:
        def __init__(self, symbol: str) -> None:
            symbols_requested.append(symbol)
            self.symbol = symbol

        @property
        def info(self) -> dict[str, float]:
            return {
                "regularMarketPrice": prices.get(self.symbol, 0.0),
                "previousClose": prices.get(self.symbol, 0.0),
            }

    monkeypatch.setattr(c10.yf, "Ticker", _Ticker)

    analyzer = c10.VIXAnalyzer()
    analyzer.rsi_calculator = MagicMock()
    analyzer.bb_calculator = MagicMock()
    monkeypatch.setattr(analyzer, "_is_update_time", lambda _current_time: True)

    analyzer._update_realtime_data()

    assert "^VIX3M" in symbols_requested
    assert "^VXV" not in symbols_requested
    assert analyzer.vix_data["VXV"].value == prices["^VIX3M"]
