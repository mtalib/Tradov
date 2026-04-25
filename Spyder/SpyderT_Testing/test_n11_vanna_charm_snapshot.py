#!/usr/bin/env python3
"""Focused tests for N11 OptionsGreeksFlowAnalyzer.get_vanna_charm_snapshot()."""

import os
import sys
import types
import math
import importlib.util as _ilu
from datetime import date, datetime
from unittest.mock import MagicMock, patch

import numpy as np


def _ensure_mod(key: str):
    parts = key.split(".")
    for i in range(1, len(parts) + 1):
        anc = ".".join(parts[:i])
        if anc not in sys.modules:
            sys.modules[anc] = types.ModuleType(anc)
    return sys.modules[key]


# ---------------------------------------------------------------------------
# Stub heavy deps before loading
# ---------------------------------------------------------------------------
for _pkg in [
    "Spyder.SpyderA_Core.SpyderA05_EventManager",
    "Spyder.SpyderC_MarketData.SpyderC03_OptionChain",
    "Spyder.SpyderF_Analysis.SpyderF06_GreeksCalculator",
    "Spyder.SpyderS_Signals.SpyderS05_GEXDEXCalculator",
    "Spyder.SpyderN_OptionsAnalytics.SpyderN09_GammaExposure",
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

_N11_PATH = os.path.join(
    _ROOT, "Spyder", "SpyderN_OptionsAnalytics", "SpyderN11_OptionsGreeksFlow.py"
)
_spec = _ilu.spec_from_file_location("_n11_flow_module", _N11_PATH)
_n11_mod = _ilu.module_from_spec(_spec)  # type: ignore[arg-type]
_spec.loader.exec_module(_n11_mod)  # type: ignore[union-attr]

OptionsGreeksFlowAnalyzer = _n11_mod.OptionsGreeksFlowAnalyzer
DealerPositioning = _n11_mod.DealerPositioning
FlowDirection = _n11_mod.FlowDirection
VannaFlow = _n11_mod.VannaFlow
CharmFlow = _n11_mod.CharmFlow
GammaFlow = _n11_mod.GammaFlow
GreeksFlowProfile = _n11_mod.GreeksFlowProfile


def _fake_profile(vanna_exp=50_000.0, charm_overnight=20_000.0,
                   total_flow=80_000.0, dealer=DealerPositioning.LONG_GAMMA):
    """Build a minimal GreeksFlowProfile for snapshot tests."""
    gamma_flow = GammaFlow(
        timestamp=datetime.now(),
        net_gamma=2.5e9,
        gamma_by_strike={},
        flip_point=575.0,
        dealer_position=dealer,
        expected_hedging=total_flow,
        confidence=0.8,
    )
    vanna_flow = VannaFlow(
        timestamp=datetime.now(),
        net_vanna=100.0,
        vanna_by_strike={},
        iv_change=0.01,
        expected_flow=vanna_exp,
        expiry_enhanced=False,
    )
    charm_flow = CharmFlow(
        timestamp=datetime.now(),
        net_charm=-50.0,
        charm_by_strike={},
        decay_schedule={1: 5000.0, 4: 8000.0, 24: charm_overnight},
        overnight_flow=charm_overnight,
    )
    return GreeksFlowProfile(
        timestamp=datetime.now(),
        gamma_flow=gamma_flow,
        vanna_flow=vanna_flow,
        charm_flow=charm_flow,
        total_expected_flow=total_flow,
        flow_direction=FlowDirection.BUYING_PRESSURE,
        key_levels=[580.0, 585.0],
        risk_assessment={"risk_factors": []},
    )


def test_snapshot_returns_all_expected_keys():
    analyzer = OptionsGreeksFlowAnalyzer()
    analyzer.get_greeks_flow_profile = MagicMock(return_value=_fake_profile())

    snap = analyzer.get_vanna_charm_snapshot()

    assert "vanna_pressure" in snap
    assert "charm_pressure" in snap
    assert "flow_imbalance_score" in snap
    assert "dealer_position" in snap
    assert "snapshot_ts" in snap


def test_snapshot_vanna_and_charm_values():
    analyzer = OptionsGreeksFlowAnalyzer()
    analyzer.get_greeks_flow_profile = MagicMock(
        return_value=_fake_profile(vanna_exp=75_000.0, charm_overnight=30_000.0)
    )

    snap = analyzer.get_vanna_charm_snapshot()

    assert snap["vanna_pressure"] == 75_000.0
    assert snap["charm_pressure"] == 30_000.0


def test_snapshot_flow_imbalance_clipped_to_minus_one_one():
    # When total_flow equals LARGE_GAMMA_FLOW the score should be exactly 1.0
    large = _n11_mod.LARGE_GAMMA_FLOW
    analyzer = OptionsGreeksFlowAnalyzer()
    analyzer.get_greeks_flow_profile = MagicMock(
        return_value=_fake_profile(total_flow=large)
    )

    snap = analyzer.get_vanna_charm_snapshot()

    assert -1.0 <= snap["flow_imbalance_score"] <= 1.0


def test_snapshot_dealer_position_matches_profile():
    analyzer = OptionsGreeksFlowAnalyzer()
    analyzer.get_greeks_flow_profile = MagicMock(
        return_value=_fake_profile(dealer=DealerPositioning.SHORT_GAMMA)
    )

    snap = analyzer.get_vanna_charm_snapshot()

    assert snap["dealer_position"] == DealerPositioning.SHORT_GAMMA.value


def test_snapshot_falls_back_on_error():
    analyzer = OptionsGreeksFlowAnalyzer()
    analyzer.get_greeks_flow_profile = MagicMock(side_effect=RuntimeError("chain unavailable"))

    snap = analyzer.get_vanna_charm_snapshot()

    assert math.isnan(snap["vanna_pressure"])
    assert math.isnan(snap["charm_pressure"])
    assert math.isnan(snap["flow_imbalance_score"])
    assert snap["dealer_position"] == "unknown"
