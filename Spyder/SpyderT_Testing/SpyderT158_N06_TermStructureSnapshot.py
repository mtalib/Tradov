#!/usr/bin/env python3
"""Focused tests for N06 term-structure snapshot generation."""

import os
import sys
import types
import importlib.util as _ilu
from datetime import datetime, timedelta
from unittest.mock import MagicMock

import numpy as np


def _ensure_mod(key: str):
    parts = key.split('.')
    for i in range(1, len(parts) + 1):
        anc = '.'.join(parts[:i])
        if anc not in sys.modules:
            sys.modules[anc] = types.ModuleType(anc)
    return sys.modules[key]


_u01 = _ensure_mod("Spyder.SpyderU_Utilities.SpyderU01_Logger")
_logger_cls = MagicMock()
_logger_cls.get_logger = MagicMock(return_value=MagicMock())
_u01.SpyderLogger = _logger_cls

_u02 = _ensure_mod("Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler")
_u02.SpyderErrorHandler = MagicMock

_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

_N06_PATH = os.path.join(
    _ROOT, "Spyder", "SpyderN_OptionsAnalytics", "SpyderN06_VolatilitySurfaceBuilder.py"
)
_spec = _ilu.spec_from_file_location("_n06_term_surface_module", _N06_PATH)
_n06_mod = _ilu.module_from_spec(_spec)  # type: ignore[arg-type]
_spec.loader.exec_module(_n06_mod)  # type: ignore[union-attr]

VolatilitySurfaceBuilder = _n06_mod.VolatilitySurfaceBuilder
VolatilitySurface = _n06_mod.VolatilitySurface
SurfaceType = _n06_mod.SurfaceType
InterpolationMethod = _n06_mod.InterpolationMethod
SurfaceAnalytics = _n06_mod.SurfaceAnalytics
SkewPattern = _n06_mod.SkewPattern


def test_n06_term_structure_snapshot_returns_expected_nodes():
    builder = VolatilitySurfaceBuilder(config={"smoothing": 0.0})
    timestamp = datetime.now() - timedelta(seconds=10)
    times = np.array([0.0, 1.0 / 365.0, 7.0 / 365.0, 30.0 / 365.0])
    moneyness = np.array([0.95, 1.0, 1.05])
    moneyness_grid, time_grid = np.meshgrid(moneyness, times)
    iv_surface = np.array([
        [0.18, 0.20, 0.19],
        [0.19, 0.21, 0.20],
        [0.22, 0.24, 0.23],
        [0.26, 0.28, 0.27],
    ])

    surface = VolatilitySurface(
        symbol="SPY",
        surface_type=SurfaceType.IMPLIED_VOLATILITY,
        timestamp=timestamp,
        underlying_price=585.0,
        risk_free_rate=0.05,
        dividend_yield=0.0,
        strikes=np.array([556.0, 585.0, 614.0]),
        expiries=np.array([
            timestamp + timedelta(days=1),
            timestamp + timedelta(days=7),
            timestamp + timedelta(days=30),
        ]),
        moneyness_grid=moneyness_grid,
        time_grid=time_grid,
        iv_surface=iv_surface,
        interpolation_method=InterpolationMethod.LINEAR,
        atm_term_structure=np.array([0.20, 0.21, 0.24, 0.28]),
        data_points=12,
    )
    builder.surfaces["SPY"] = surface
    builder.analyze_surface = MagicMock(return_value=SurfaceAnalytics(
        term_structure_shape='contango',
        term_structure_slope=1.0,
        skew_pattern=SkewPattern.NORMAL,
        skew_steepness=0.0,
        put_wing_slope=0.0,
        call_wing_slope=0.0,
        smile_curvature=0.0,
        atm_volatility=0.20,
        risk_reversal_25d=0.012,
        butterfly_25d=0.008,
        smoothness_score=0.9,
        data_coverage=1.0,
        interpolation_quality=0.95,
        rich_strikes=[],
        cheap_strikes=[],
        arbitrage_opportunities=[],
    ))

    snapshot = builder.get_term_structure_snapshot("SPY")

    assert snapshot["atm_iv_0dte"] == 0.20
    assert snapshot["atm_iv_1dte"] == 0.21
    assert snapshot["atm_iv_7dte"] == 0.24
    assert snapshot["atm_iv_30dte"] == 0.28
    assert snapshot["term_slope_0_7"] == ((0.24 - 0.20) / (7.0 / 365.0))
    assert snapshot["term_slope_7_30"] == ((0.28 - 0.24) / (23.0 / 365.0))
    assert snapshot["rr_25d"] == 0.012
    assert snapshot["fly_25d"] == 0.008
    assert 0.0 <= snapshot["surface_confidence"] <= 1.0
    assert snapshot["surface_age_ms"] >= 0


def test_n06_term_structure_snapshot_degrades_confidence_for_stale_surface():
    builder = VolatilitySurfaceBuilder(config={"smoothing": 0.0})
    timestamp = datetime.now() - timedelta(minutes=5)
    times = np.array([0.0, 7.0 / 365.0])
    moneyness = np.array([1.0, 1.05])
    moneyness_grid, time_grid = np.meshgrid(moneyness, times)
    iv_surface = np.array([
        [0.20, np.nan],
        [0.23, 0.24],
    ])
    surface = VolatilitySurface(
        symbol="SPY",
        surface_type=SurfaceType.IMPLIED_VOLATILITY,
        timestamp=timestamp,
        underlying_price=585.0,
        risk_free_rate=0.05,
        dividend_yield=0.0,
        strikes=np.array([585.0, 614.0]),
        expiries=np.array([timestamp + timedelta(days=1), timestamp + timedelta(days=7)]),
        moneyness_grid=moneyness_grid,
        time_grid=time_grid,
        iv_surface=iv_surface,
        interpolation_method=InterpolationMethod.LINEAR,
        atm_term_structure=np.array([0.20, 0.23]),
        data_points=3,
    )
    builder.surfaces["SPY"] = surface
    builder.analyze_surface = MagicMock(return_value=SurfaceAnalytics(
        term_structure_shape='flat',
        term_structure_slope=0.0,
        skew_pattern=SkewPattern.FLAT,
        skew_steepness=0.0,
        put_wing_slope=0.0,
        call_wing_slope=0.0,
        smile_curvature=0.0,
        atm_volatility=0.20,
        risk_reversal_25d=0.0,
        butterfly_25d=0.0,
        smoothness_score=0.0,
        data_coverage=0.0,
        interpolation_quality=0.0,
        rich_strikes=[],
        cheap_strikes=[],
        arbitrage_opportunities=[],
    ))

    snapshot = builder.get_term_structure_snapshot("SPY")

    assert snapshot["surface_age_ms"] >= 300000 - 1000
    assert snapshot["surface_confidence"] < 0.8
