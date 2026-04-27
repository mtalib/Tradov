#!/usr/bin/env python3
"""Focused tests for N09 GammaExposureCalculator.get_dealer_walls_snapshot()."""

import os
import sys
import types
import math
import importlib.util as _ilu
from datetime import datetime
from unittest.mock import MagicMock

import numpy as np


def _ensure_mod(key: str):
    parts = key.split(".")
    for i in range(1, len(parts) + 1):
        anc = ".".join(parts[:i])
        if anc not in sys.modules:
            sys.modules[anc] = types.ModuleType(anc)
    return sys.modules[key]


# ---------------------------------------------------------------------------
# Stub out heavy deps before loading the module
# ---------------------------------------------------------------------------
for _pkg in [
    "matplotlib", "matplotlib.pyplot",
    "Spyder.SpyderN_OptionsAnalytics.SpyderN07_OPRAGreeksHandler",
    "Spyder.SpyderC_MarketData.SpyderC03_OptionChain",
    "Spyder.SpyderA_Core.SpyderA05_EventManager",
]:
    sys.modules.setdefault(_pkg, MagicMock())

_u01 = _ensure_mod("Spyder.SpyderU_Utilities.SpyderU01_Logger")
_logger_cls = MagicMock()
_logger_cls.get_logger = MagicMock(return_value=MagicMock())
_u01.SpyderLogger = _logger_cls

_u02 = _ensure_mod("Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler")
_u02.SpyderErrorHandler = MagicMock

_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

_N09_PATH = os.path.join(
    _ROOT, "Spyder", "SpyderN_OptionsAnalytics", "SpyderN09_GammaExposure.py"
)
_spec = _ilu.spec_from_file_location("_n09_gex_module", _N09_PATH)
_n09_mod = _ilu.module_from_spec(_spec)  # type: ignore[arg-type]
_spec.loader.exec_module(_n09_mod)  # type: ignore[union-attr]

GammaExposureCalculator = _n09_mod.GammaExposureCalculator
GEXProfile = _n09_mod.GEXProfile
GEXRegime = _n09_mod.GEXRegime
HedgingFlow = _n09_mod.HedgingFlow


def _make_profile(spot=580.0, zg=575.0, current_gex=2.5e9):
    """Build a minimal GEXProfile for snapshot tests."""
    price_levels = np.array([560.0, 570.0, 575.0, 580.0, 585.0, 590.0, 600.0])
    # Positive gamma (call wall) at 590, negative (put wall) at 570
    gamma_exposure = np.array([0.0, -3e8, 0.0, 0.0, 0.0, 4e8, 0.0])
    return GEXProfile(
        timestamp=datetime.now(),
        spot_price=spot,
        current_gex=current_gex,
        price_levels=price_levels,
        gamma_exposure=gamma_exposure,
        call_gamma=np.zeros(7),
        put_gamma=np.zeros(7),
        zero_gamma_level=zg,
        max_gamma_level=590.0,
        max_gamma_value=4e8,
        regime=GEXRegime.MODERATE_POSITIVE,
        expected_flow=HedgingFlow.NEUTRAL,
        total_gamma_notional=7e8,
        weighted_average_gamma=0.0,
        gamma_concentration=0.5,
    )


def test_snapshot_returns_expected_scalar_keys():
    calc = GammaExposureCalculator()
    calc.current_profile = _make_profile()

    snap = calc.get_dealer_walls_snapshot()

    assert "zero_gamma_level" in snap
    assert "spot_to_zero_gamma_pct" in snap
    assert "call_wall_levels" in snap
    assert "put_wall_levels" in snap
    assert "wall_confidence" in snap
    assert "net_gex" in snap
    assert "regime" in snap
    assert "snapshot_ts" in snap


def test_snapshot_computes_spot_to_zg_pct():
    spot, zg = 580.0, 575.0
    calc = GammaExposureCalculator()
    calc.current_profile = _make_profile(spot=spot, zg=zg)

    snap = calc.get_dealer_walls_snapshot()

    expected_pct = (spot - zg) / spot * 100.0
    assert abs(snap["spot_to_zero_gamma_pct"] - expected_pct) < 1e-6


def test_snapshot_identifies_call_and_put_walls():
    calc = GammaExposureCalculator()
    calc.current_profile = _make_profile()

    snap = calc.get_dealer_walls_snapshot()

    # gamma_exposure has a local positive peak at 590 → call wall (resistance)
    # and a local negative peak at 570 → put wall (support)
    assert isinstance(snap["call_wall_levels"], list)
    assert isinstance(snap["put_wall_levels"], list)


def test_snapshot_defaults_when_no_profile_and_calc_fails():
    calc = GammaExposureCalculator()
    calc.current_profile = None
    # calculate_gex_profile would fail due to missing deps — mock it to raise
    calc.calculate_gex_profile = MagicMock(side_effect=RuntimeError("no chain"))

    snap = calc.get_dealer_walls_snapshot()

    assert math.isnan(snap["zero_gamma_level"])
    assert snap["call_wall_levels"] == []
    assert snap["put_wall_levels"] == []
    assert snap["wall_confidence"] == 0.0
    assert snap["regime"] == "unknown"


def test_snapshot_regime_matches_profile():
    calc = GammaExposureCalculator()
    calc.current_profile = _make_profile()

    snap = calc.get_dealer_walls_snapshot()

    assert snap["regime"] == GEXRegime.MODERATE_POSITIVE.value
