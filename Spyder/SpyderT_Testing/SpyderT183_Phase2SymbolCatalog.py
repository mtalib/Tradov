#!/usr/bin/env python3
"""Phase 2 guardrails for canonical symbol governance."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from Spyder.SpyderU_Utilities.SpyderU49_SymbolCatalog import (
    get_backend_symbol_groups,
    get_computed_or_event_symbols,
    get_deprecated_symbols,
    get_market_overview_symbols,
    get_market_overview_symbol_set,
    get_optional_symbols,
    get_quote_symbol_basket,
    get_quote_symbol_remap,
    get_worker_live_data_keys,
)


def test_market_overview_symbols_match_dashboard_data_constant() -> None:
    """DashboardData must consume canonical market-overview symbols."""
    from Spyder.SpyderG_GUI.SpyderG06_DashboardData import MARKET_SYMBOLS

    assert MARKET_SYMBOLS == get_market_overview_symbols()


def test_market_overview_symbols_match_trading_dashboard_constant() -> None:
    """Trading dashboard panel source must match canonical market-overview symbols."""
    pytest.importorskip("PySide6")
    from Spyder.SpyderG_GUI.SpyderG05_TradingDashboard import MARKET_SYMBOLS

    assert MARKET_SYMBOLS == get_market_overview_symbols()


def test_quote_basket_excludes_computed_and_event_only_symbols() -> None:
    """Computed and event-only rows must never be direct quote fetch targets."""
    quote_basket = set(get_quote_symbol_basket())
    computed_or_event = get_computed_or_event_symbols()

    # Computed/event keys are display symbols and must not leak into quote calls.
    assert not quote_basket.intersection(computed_or_event)


def test_quote_proxy_remap_is_explicit_for_dxy() -> None:
    """DXY must remain an explicit proxy remap via UUP."""
    basket = get_quote_symbol_basket()
    remap = get_quote_symbol_remap()

    assert "UUP" in basket
    assert "DXY" not in basket
    assert remap.get("UUP") == "DXY"


def test_market_data_worker_uses_canonical_quote_basket_builder() -> None:
    """Slow, fast, and EOD paths must share one quote basket policy."""
    pytest.importorskip("PySide6")
    from Spyder.SpyderG_GUI.SpyderG18_MarketDataWorker import _build_quote_symbol_basket

    assert _build_quote_symbol_basket() == get_quote_symbol_basket()


def test_paper_account_balance_source_aliases(monkeypatch: pytest.MonkeyPatch) -> None:
    """Paper account source env should always normalize to SpyderBox local."""
    pytest.importorskip("PySide6")
    from Spyder.SpyderG_GUI import SpyderG18_MarketDataWorker as worker

    monkeypatch.delenv("SPYDER_PAPER_ACCOUNT_SOURCE", raising=False)
    assert worker._paper_account_balance_source() == worker.PAPER_ACCOUNT_SOURCE_SPYDERBOX_LOCAL

    monkeypatch.setenv("SPYDER_PAPER_ACCOUNT_SOURCE", "spyderbox")
    assert worker._paper_account_balance_source() == worker.PAPER_ACCOUNT_SOURCE_SPYDERBOX_LOCAL

    monkeypatch.setenv("SPYDER_PAPER_ACCOUNT_SOURCE", "local")
    assert worker._paper_account_balance_source() == worker.PAPER_ACCOUNT_SOURCE_SPYDERBOX_LOCAL

    monkeypatch.setenv("SPYDER_PAPER_ACCOUNT_SOURCE", "tradier_sandbox")
    assert worker._paper_account_balance_source() == worker.PAPER_ACCOUNT_SOURCE_SPYDERBOX_LOCAL

    monkeypatch.setenv("SPYDER_PAPER_ACCOUNT_SOURCE", "unexpected_value")
    assert worker._paper_account_balance_source() == worker.PAPER_ACCOUNT_SOURCE_SPYDERBOX_LOCAL


def test_load_spyderbox_snapshot_from_state_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """State-file fallback should provide local paper equity and buying power."""
    pytest.importorskip("PySide6")
    from Spyder.SpyderG_GUI import SpyderG18_MarketDataWorker as worker

    state_path = tmp_path / "paper_state.json"
    state_path.write_text(json.dumps({"_cash": 12345.67}), encoding="utf-8")

    monkeypatch.setenv("SPYDER_PAPER_ACCOUNT_STATE_FILE", str(state_path))
    snapshot = worker._load_spyderbox_paper_account_snapshot()

    assert snapshot == (12345.67, 12345.67)


def test_fetch_balance_only_prefers_local_spyderbox_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Balance-only path should emit SpyderBox local snapshot in paper mode."""
    pytest.importorskip("PySide6")
    from Spyder.SpyderG_GUI import SpyderG18_MarketDataWorker as worker

    emitted: list[tuple[float, float]] = []

    class _SignalStub:
        def emit(self, equity: float, buying_power: float) -> None:
            emitted.append((equity, buying_power))

    class _WorkerStub:
        balance_updated = _SignalStub()

    monkeypatch.setenv("TRADING_MODE", "paper")
    monkeypatch.setenv("SPYDER_PAPER_ACCOUNT_SOURCE", "spyderbox_local")
    monkeypatch.setattr(worker, "_load_spyderbox_paper_account_snapshot", lambda: (101000.0, 99000.0))
    monkeypatch.setattr(worker, "TRADIER_AVAILABLE", False)

    worker.ThreadSafeMarketDataWorker._fetch_balance_only(_WorkerStub())

    assert emitted == [(101000.0, 99000.0)]


def test_fetch_balance_only_has_no_tradier_fallback_when_local_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Paper-mode balance fetch must fail closed when local snapshot is unavailable."""
    pytest.importorskip("PySide6")
    from Spyder.SpyderG_GUI import SpyderG18_MarketDataWorker as worker

    emitted: list[tuple[float, float]] = []

    class _SignalStub:
        def emit(self, equity: float, buying_power: float) -> None:
            emitted.append((equity, buying_power))

    class _WorkerStub:
        balance_updated = _SignalStub()

    class _UnexpectedTradierClient:
        def __init__(self, *args, **kwargs):
            raise AssertionError("Tradier fallback must not be used in paper mode")

    monkeypatch.setenv("TRADING_MODE", "paper")
    monkeypatch.setenv("SPYDER_PAPER_ACCOUNT_SOURCE", "tradier_sandbox")
    monkeypatch.setattr(worker, "_load_spyderbox_paper_account_snapshot", lambda: None)
    monkeypatch.setattr(worker, "TRADIER_AVAILABLE", True)
    monkeypatch.setattr(worker, "TradierClient", _UnexpectedTradierClient)

    worker.ThreadSafeMarketDataWorker._fetch_balance_only(_WorkerStub())

    assert emitted == []


def test_deprecated_symbols_are_not_part_of_market_overview() -> None:
    """Deprecated compatibility symbols must stay out of Market Overview."""
    deprecated = get_deprecated_symbols()
    overview = get_market_overview_symbol_set()

    assert deprecated == set()
    assert not deprecated.intersection(overview)


def test_optional_symbols_include_recent_decision_list_metrics() -> None:
    """Optional set should explicitly track staged/derived metrics added recently."""
    optional = get_optional_symbols()

    assert {"NYMO", "$VOLD", "RVOL", "WRS", "PSR", "PMR"}.issubset(optional)


def test_worker_live_data_snapshot_keys_are_explicit() -> None:
    """Base worker-written live_data keys should stay stable and intentional."""
    keys = get_worker_live_data_keys()

    assert {"SPY", "SPX", "VIX", "VIX9D", "VXV", "VVIX", "SKEW"}.issubset(keys)
    assert {"DIA", "QQQ", "IWM", "TLT", "HYG", "LQD", "GLD", "USO", "DXY"}.issubset(keys)
    assert {"XLK", "XLF", "CPC", "RVOL"}.issubset(keys)
    assert "RUT" in keys
    assert "UUP" not in keys


def test_backend_symbol_groups_stay_aligned_between_c01_and_catalog() -> None:
    """C01 symbol groups must be derived from the canonical backend view."""
    from Spyder.SpyderC_MarketData.SpyderC01_DataFeed import SYMBOL_GROUPS

    assert SYMBOL_GROUPS == get_backend_symbol_groups()


def test_backend_symbol_groups_stay_aligned_between_c17_and_catalog() -> None:
    """C17 visible symbol defaults must match canonical backend groups."""
    from Spyder.SpyderC_MarketData.SpyderC17_MarketConfigManager import DEFAULT_SYMBOL_CONFIG

    backend_groups = get_backend_symbol_groups()
    visible = DEFAULT_SYMBOL_CONFIG["visible_symbols"]

    assert visible["S&P_CORE"]["symbols"] == backend_groups["CORE"]
    assert visible["VOLATILITY"]["symbols"] == backend_groups["VOLATILITY"]
    assert visible["MARKET_INTERNALS"]["symbols"] == backend_groups["INTERNALS"]
    assert visible["MAJOR_INDICES"]["symbols"] == backend_groups["INDICES"]
    assert visible["BONDS_CREDIT"]["symbols"] == backend_groups["FIXED_INCOME"]
    assert visible["CORRELATIONS"]["symbols"] == backend_groups["CORRELATIONS"]
