#!/usr/bin/env python3
"""Focused regressions for SPX/SPXW symbol handling and paper-engine option detection."""

from __future__ import annotations

import pytest

from Spyder.SpyderB_Broker.SpyderB40_TradierClient import build_option_symbol
from Spyder.SpyderR_Runtime.SpyderR02_PaperEngine import (
    DEFAULT_OPTION_COMMISSION,
    PaperTradingEngine,
    _looks_like_option_symbol,
)


def test_build_option_symbol_allows_spxw_non_etf_strike_grid() -> None:
    symbol = build_option_symbol("SPXW", "2026-06-19", "C", 5987.37)
    assert symbol.startswith("SPXW260619C")


def test_build_option_symbol_still_enforces_etf_strike_grid_for_spy() -> None:
    with pytest.raises(ValueError, match="0.05 increments"):
        build_option_symbol("SPY", "2026-06-19", "P", 5987.371)


def test_looks_like_option_symbol_detects_occ_spxw_symbol() -> None:
    assert _looks_like_option_symbol("SPXW260619C05900000") is True


def test_paper_engine_commission_uses_option_rate_for_occ_symbol() -> None:
    engine = PaperTradingEngine()
    commission = engine._calculate_commission("SPXW260619P05800000", 3)
    assert commission == pytest.approx(3 * DEFAULT_OPTION_COMMISSION)
