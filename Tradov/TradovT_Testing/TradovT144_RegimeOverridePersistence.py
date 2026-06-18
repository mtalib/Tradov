#!/usr/bin/env python3
"""Tests for the user-selectable market-regime override and its persistence.

Covers:
  * the pure JSON store (U50): round-trip, clear, and tolerance of missing /
    corrupt files,
  * that the GUI option set (``REGIME_OPTIONS``) stays in sync with D31's
    ``MarketRegime`` enum (no drift),
  * D31 override coercion, and the load / save / disk-sync helpers that make the
    override survive restarts and pick up external (GUI) writes.
"""

from __future__ import annotations

import importlib

from Tradov.TradovU_Utilities import TradovU50_RegimeOverrideStore as store


class _StubEventManager:
    def __init__(self):
        self.handlers = {}

    def subscribe(self, event_type, handler):
        self.handlers.setdefault(event_type, []).append(handler)

    def emit(self, *args, **kwargs):
        return None


def _d31():
    return importlib.import_module(
        "Tradov.TradovD_Strategies.TradovD31_StrategyOrchestrator"
    )


# --------------------------------------------------------------------------- #
# Pure store (U50)
# --------------------------------------------------------------------------- #
def test_store_round_trip(tmp_path):
    path = tmp_path / "regime_override.json"
    assert store.load_regime_override(path) is None          # missing -> auto
    assert store.save_regime_override("crisis", path) is True
    assert store.load_regime_override(path) == "crisis"
    assert store.save_regime_override(None, path) is True     # clear
    assert store.load_regime_override(path) is None


def test_store_clear_helper(tmp_path):
    path = tmp_path / "regime_override.json"
    store.save_regime_override("recovery", path)
    assert store.clear_regime_override(path) is True
    assert store.load_regime_override(path) is None


def test_store_normalizes_auto_tokens(tmp_path):
    path = tmp_path / "regime_override.json"
    for token in ("auto", "AUTO", "", "none"):
        store.save_regime_override(token, path)
        assert store.load_regime_override(path) is None


def test_store_tolerates_corrupt_file(tmp_path):
    path = tmp_path / "regime_override.json"
    path.write_text("{ not valid json")
    assert store.load_regime_override(path) is None          # never raises


def test_regime_options_match_enum_no_drift():
    """The GUI selector options must mirror D31's MarketRegime values exactly."""
    MarketRegime = _d31().MarketRegime
    enum_values = {r.value for r in MarketRegime}
    option_tokens = {tok for tok, _label in store.REGIME_OPTIONS if tok is not None}
    assert option_tokens == enum_values
    # And the "auto" sentinel must be present exactly once.
    assert sum(1 for tok, _ in store.REGIME_OPTIONS if tok is None) == 1


# --------------------------------------------------------------------------- #
# D31 coercion
# --------------------------------------------------------------------------- #
def test_coerce_regime_accepts_value_name_enum_and_auto():
    mod = _d31()
    SO, MR = mod.StrategyOrchestrator, mod.MarketRegime
    assert SO._coerce_regime("crisis") == MR.CRISIS
    assert SO._coerce_regime("BULL_LOW_VOL") == MR.BULL_LOW_VOL
    assert SO._coerce_regime(MR.RECOVERY) == MR.RECOVERY
    assert SO._coerce_regime("auto") is None
    assert SO._coerce_regime(None) is None


def test_coerce_regime_rejects_unknown():
    SO = _d31().StrategyOrchestrator
    try:
        SO._coerce_regime("not_a_regime")
    except ValueError:
        return
    raise AssertionError("expected ValueError for unknown regime")


# --------------------------------------------------------------------------- #
# D31 persistence helpers (load on init, save on set, sync from disk)
# --------------------------------------------------------------------------- #
def _make_orchestrator(tmp_path):
    orch = _d31().StrategyOrchestrator(event_manager=_StubEventManager())
    orch._regime_override_path = tmp_path / "regime_override.json"
    return orch


def test_set_and_clear_persist_to_disk(tmp_path):
    mod = _d31()
    MR = mod.MarketRegime
    orch = _make_orchestrator(tmp_path)

    effective = orch.set_regime_override("crisis")
    assert effective == MR.CRISIS
    assert orch.market_regime.current_regime == MR.CRISIS
    assert store.load_regime_override(orch._regime_override_path) == "crisis"

    orch.clear_regime_override()
    assert orch._regime_override is None
    assert store.load_regime_override(orch._regime_override_path) is None


def test_load_regime_override_on_init(tmp_path):
    mod = _d31()
    MR = mod.MarketRegime
    orch = _make_orchestrator(tmp_path)
    store.save_regime_override("recovery", orch._regime_override_path)

    orch._load_regime_override()
    assert orch._regime_override == MR.RECOVERY
    assert orch.market_regime.current_regime == MR.RECOVERY


def test_sync_picks_up_external_write(tmp_path):
    mod = _d31()
    MR = mod.MarketRegime
    orch = _make_orchestrator(tmp_path)
    assert orch._regime_override is None

    # Simulate the GUI writing the file while no live override is set.
    store.save_regime_override("bear_high_vol", orch._regime_override_path)
    orch._sync_regime_override_from_disk()
    assert orch._regime_override == MR.BEAR_HIGH_VOL
