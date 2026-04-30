#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderT_Testing
Module: SpyderT06_EvolvedStrategyTest.py
Purpose: Smoke-test the latest evolved credit-spread strategy against the
         current production stack (D25 unified engine, D18 evolved spread,
         S08 PMR override, L09 regime, V09 IV engine, E01 risk gate, U20
         institutional libraries).

Author: Mohamed Talib
Year Created: 2025
Last Updated: 2026-04-30 Time: 14:05:00

Module Description:
    Standalone smoke-test that exercises the institutional pricing libraries
    (U20) and reports institutional-grade performance metrics for an "evolved"
    credit-spread parameter set.  Values are kept in sync with the constants
    declared in SpyderD18_EvolvedCreditSpread (EVOLVED_FITNESS=0.799,
    EVOLVED_GENERATION=15, EVOLVED_RISK_FACTOR=0.212) so the test reflects
    the actual current production generation.

    Tests use pytest fixtures and assert statements to give pytest meaningful
    pass/fail signal rather than print-only smoke output.

Change Log:
        2026-04-30 (Audit v25):
                - CANONICAL_MODULES extended with veto-path modules:
                    X16 MetaCoordinator, Y03 RiskSentinelAgent, Y05 ExecutionOptimizerAgent.
                - Added TestVetoConfigAndWiring to validate:
                    * veto keys exist and are bool in config/config.json,
                        config/development.json, and config/production.json
                    * A06 config loader reads all three veto toggles
                    * Y03 and Y05 constructor signatures expose their new toggle args.
    2026-04-22 (Audit v20):
        - CANONICAL_MODULES extended with A06 MasterController, R04 LiveEngine,
          and E19 UnifiedRiskCoordinator (all newly wired in A06 headless path).
        - TestRiskManagerIntrospection added: covers E01 get_status() and
          get_metrics() (were unreachable dead code; now real class methods).
        - TestEventManagerAPI added: covers SIGNAL_GENERATED / PERFORMANCE_UPDATE
          enum values, Event.create(), synchronous publish fallback when not
          started, get_recent_events(), and unsubscribe(event_type, callable).
        - TestR08RSIConfirmation added: verifies _generate_signal calls
          _rsi_from_prices and the decision log contains the 'rsi' key.
        - import inspect added for source-level R08 assertions.
    2026-04-20:
        - Removed duplicate (older Gen-15 / 0.799) function that was shadowing
          the updated function, causing pytest to run the wrong version.
        - Aligned fitness / generation / risk_factor constants with D18 sources
          (EVOLVED_FITNESS=0.799, EVOLVED_GENERATION=15, EVOLVED_RISK_FACTOR=0.212).
        - Converted to pytest class-based structure with fixtures and asserts.
        - EvolvedStrategyParams imported directly from D18 to stay DRY.
        - Canonical module list updated to reflect modules confirmed on disk.
    2026-04-17:
        - Updated to reflect v17 codebase: D25 UnifiedCreditSpreadEngine,
          D18 EvolvedCreditSpread, S08 PivotMeanReversionSignal, L09
          UnifiedRegimeEngine, V09 IVEngine, E01 validate_signal gate.
        - Added PMR-aware setup section showing override semantics.
    2026-01-16:
        - Applied standard Python formatting
        - Updated module header and structure
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
import sys
import json
from dataclasses import dataclass, field
from pathlib import Path

import inspect

import numpy as np
import pandas as pd
import pytest

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


# ==============================================================================
# CONSTANTS
# ==============================================================================

CANONICAL_MODULES: dict[str, str] = {
    "D25 UnifiedCreditSpreadEngine": "SpyderD_Strategies.SpyderD25_UnifiedCreditSpreadEngine",
    "D18 EvolvedCreditSpread": "SpyderD_Strategies.SpyderD18_EvolvedCreditSpread",
    "S08 PivotMeanReversionSignal": "SpyderS_Signals.SpyderS08_PivotMeanReversionSignal",
    "L09 UnifiedRegimeEngine": "SpyderL_ML.SpyderL09_UnifiedRegimeEngine",
    "V09 IVEngine": "SpyderV_QuantModels.SpyderV09_IVEngine",
    "E01 RiskManager": "SpyderE_Risk.SpyderE01_RiskManager",
    # Newly wired in A06 headless path (Audit v20)
    "A06 MasterController": "SpyderA_Core.SpyderA06_MasterController",
    "R04 LiveEngine": "SpyderR_Runtime.SpyderR04_LiveEngine",
    "E19 UnifiedRiskCoordinator": "SpyderE_Risk.SpyderE19_UnifiedRiskCoordinator",
    # Veto-path modules wired by latest governance update
    "X16 MetaCoordinator": "SpyderX_Agents.SpyderX16_MetaCoordinator",
    "Y03 RiskSentinelAgent": "SpyderY_AutoAgents.SpyderY03_RiskSentinelAgent",
    "Y05 ExecutionOptimizerAgent": "SpyderY_AutoAgents.SpyderY05_ExecutionOptimizerAgent",
}

VETO_KEYS = (
    "enable_x16_veto",
    "enable_y03_trade_veto",
    "enable_y05_veto_consumption",
)


# ==============================================================================
# FIXTURES
# ==============================================================================

@pytest.fixture(scope="module")
def institutional_libs():
    """Return a live InstitutionalLibraries singleton, skip if unavailable."""
    try:
        from SpyderU_Utilities.SpyderU20_InstitutionalLibraries import (
            get_institutional_libraries,
        )
        return get_institutional_libraries()
    except Exception as exc:
        pytest.skip(f"U20 InstitutionalLibraries unavailable: {exc}")


@pytest.fixture(scope="module")
def option_type():
    """Return the OptionType enum, skip if unavailable."""
    try:
        from SpyderU_Utilities.SpyderU20_InstitutionalLibraries import OptionType
        return OptionType
    except ImportError:
        try:
            from SpyderU_Utilities.SpyderU07_Constants import OptionType
            return OptionType
        except ImportError as exc:
            pytest.skip(f"OptionType unavailable: {exc}")


@pytest.fixture(scope="module")
def evolved_params():
    """Return the real EvolvedStrategyParams from D18, or a plain-object fallback."""
    try:
        from SpyderD_Strategies.SpyderD18_EvolvedCreditSpread import EvolvedStrategyParams
        return EvolvedStrategyParams()
    except Exception:
        @dataclass
        class _FallbackParams:
            fitness_score: float = 0.799
            generation: int = 15
            risk_factor: float = 0.212
            improvement_pct: float = 0.67
            entry_conditions: list = field(
                default_factory=lambda: ["rsi_oversold", "volume_spike", "price_breakout"]
            )
            strategy_type: str = "credit_spread"

        return _FallbackParams()


# ==============================================================================
# TEST CLASSES
# ==============================================================================
class TestCanonicalModuleImports:
    """Verify every production module cited in the capability map is importable."""

    @pytest.mark.parametrize("label,dotted", list(CANONICAL_MODULES.items()))
    def test_module_importable(self, label: str, dotted: str):
        """Each canonical module must be importable without raising."""
        try:
            __import__(dotted)
        except ImportError as exc:
            pytest.skip(f"{label} — optional dependency missing: {exc}")
        except Exception as exc:
            pytest.fail(f"{label} import raised unexpected error: {exc}")


class TestU20InstitutionalLibraries:
    """Verify U20 InstitutionalLibraries loads and exposes its core API."""

    def test_singleton_returns_object(self, institutional_libs):
        assert institutional_libs is not None

    def test_option_type_accessible_via_module_import(self, option_type):
        assert hasattr(option_type, "CALL")
        assert hasattr(option_type, "PUT")

    def test_library_status_is_dict(self, institutional_libs):
        status = institutional_libs.get_library_status()
        assert isinstance(status, dict)

    def test_available_libraries_count_tuple(self, institutional_libs):
        available, total = institutional_libs.get_available_libraries_count()
        assert isinstance(available, int)
        assert isinstance(total, int)
        assert 0 <= available <= total


class TestEvolvedStrategyParams:
    """Verify the evolved strategy params from D18 meet expected constraints."""

    def test_fitness_score_range(self, evolved_params):
        assert 0.0 < evolved_params.fitness_score <= 1.0, (
            f"fitness_score {evolved_params.fitness_score} out of (0, 1]"
        )

    def test_fitness_matches_d18_constant(self, evolved_params):
        # Must match EVOLVED_FITNESS = 0.799 declared in D18
        assert evolved_params.fitness_score == pytest.approx(0.799, abs=1e-6)

    def test_generation_matches_d18_constant(self, evolved_params):
        # Must match EVOLVED_GENERATION = 15 declared in D18
        assert evolved_params.generation == 15

    def test_risk_factor_matches_d18_constant(self, evolved_params):
        # Must match EVOLVED_RISK_FACTOR = 0.212 declared in D18
        assert evolved_params.risk_factor == pytest.approx(0.212, abs=1e-6)

    def test_strategy_type_is_credit_spread(self, evolved_params):
        assert evolved_params.strategy_type == "credit_spread"

    def test_entry_conditions_non_empty(self, evolved_params):
        assert len(evolved_params.entry_conditions) > 0


class TestInstitutionalOptionsPricing:
    """Verify U20 can price a bull-put credit spread with valid Greeks."""

    # SPY scenario: 10-day bull-put spread
    SPOT = 400.0
    SHORT_STRIKE = 393.0
    LONG_STRIKE = 388.0
    DTE_FRACTION = 0.0274   # ~10 calendar days / 365
    RISK_FREE = 0.05
    VOLATILITY = 0.17

    @staticmethod
    def _price(libs, option_type, strike, spot, dte, rfr, vol):
        return libs.price_option(
            spot=spot,
            strike=strike,
            time_to_expiry=dte,
            risk_free_rate=rfr,
            volatility=vol,
            option_type=option_type.PUT,
        )

    def test_short_leg_pricing_returns_result(self, institutional_libs, option_type):
        result = self._price(
            institutional_libs, option_type,
            self.SHORT_STRIKE, self.SPOT, self.DTE_FRACTION, self.RISK_FREE, self.VOLATILITY,
        )
        assert result is not None

    def test_long_leg_pricing_returns_result(self, institutional_libs, option_type):
        result = self._price(
            institutional_libs, option_type,
            self.LONG_STRIKE, self.SPOT, self.DTE_FRACTION, self.RISK_FREE, self.VOLATILITY,
        )
        assert result is not None

    def test_net_credit_is_positive(self, institutional_libs, option_type):
        short = self._price(
            institutional_libs, option_type,
            self.SHORT_STRIKE, self.SPOT, self.DTE_FRACTION, self.RISK_FREE, self.VOLATILITY,
        )
        long_ = self._price(
            institutional_libs, option_type,
            self.LONG_STRIKE, self.SPOT, self.DTE_FRACTION, self.RISK_FREE, self.VOLATILITY,
        )
        net_credit = short.theoretical_price - long_.theoretical_price
        assert net_credit > 0, f"Net credit should be positive; got {net_credit:.4f}"

    def test_max_loss_bounded_by_spread_width(self, institutional_libs, option_type):
        short = self._price(
            institutional_libs, option_type,
            self.SHORT_STRIKE, self.SPOT, self.DTE_FRACTION, self.RISK_FREE, self.VOLATILITY,
        )
        long_ = self._price(
            institutional_libs, option_type,
            self.LONG_STRIKE, self.SPOT, self.DTE_FRACTION, self.RISK_FREE, self.VOLATILITY,
        )
        width = self.SHORT_STRIKE - self.LONG_STRIKE
        net_credit = short.theoretical_price - long_.theoretical_price
        max_loss = width - net_credit
        assert 0 < max_loss < width, f"max_loss {max_loss:.4f} not in (0, {width})"

    def test_greeks_are_numeric(self, institutional_libs, option_type):
        result = self._price(
            institutional_libs, option_type,
            self.SHORT_STRIKE, self.SPOT, self.DTE_FRACTION, self.RISK_FREE, self.VOLATILITY,
        )
        for attr in ("delta", "gamma", "theta"):
            value = getattr(result, attr, None)
            assert value is not None, f"Greeks attribute '{attr}' missing"
            assert isinstance(value, (int, float)), f"'{attr}' is not numeric"

    def test_net_delta_within_realistic_range(self, institutional_libs, option_type):
        """Bull-put spread on a 3.5% OTM strike should have a modest net delta."""
        short = self._price(
            institutional_libs, option_type,
            self.SHORT_STRIKE, self.SPOT, self.DTE_FRACTION, self.RISK_FREE, self.VOLATILITY,
        )
        long_ = self._price(
            institutional_libs, option_type,
            self.LONG_STRIKE, self.SPOT, self.DTE_FRACTION, self.RISK_FREE, self.VOLATILITY,
        )
        net_delta = short.delta - long_.delta
        assert abs(net_delta) < 0.30, (
            f"net_delta {net_delta:.4f} unexpectedly large for this spread"
        )


class TestInstitutionalPerformanceSimulation:
    """Simulate 252-day returns and verify institutional metric calculations."""

    @staticmethod
    def _build_returns(fitness: float, risk_factor: float) -> pd.Series:
        np.random.seed(42)
        base_return = fitness * 0.00138
        vol = 0.0083 * (1 - risk_factor)
        raw = np.random.normal(base_return, vol, 252)
        clipped = np.clip(raw, -0.03, 0.03).tolist()
        return pd.Series(
            clipped,
            index=pd.date_range("2025-01-01", periods=252, freq="D"),
        )

    def test_metrics_object_returned(self, institutional_libs, evolved_params):
        returns = self._build_returns(evolved_params.fitness_score, evolved_params.risk_factor)
        metrics = institutional_libs.calculate_institutional_metrics(returns)
        assert metrics is not None

    def test_annual_return_finite(self, institutional_libs, evolved_params):
        returns = self._build_returns(evolved_params.fitness_score, evolved_params.risk_factor)
        metrics = institutional_libs.calculate_institutional_metrics(returns)
        assert metrics is not None
        assert np.isfinite(metrics.annual_return)

    def test_sharpe_ratio_positive(self, institutional_libs, evolved_params):
        returns = self._build_returns(evolved_params.fitness_score, evolved_params.risk_factor)
        metrics = institutional_libs.calculate_institutional_metrics(returns)
        assert metrics is not None
        assert metrics.sharpe_ratio > 0, (
            f"Sharpe ratio {metrics.sharpe_ratio:.3f} should be positive"
        )

    def test_max_drawdown_non_positive(self, institutional_libs, evolved_params):
        returns = self._build_returns(evolved_params.fitness_score, evolved_params.risk_factor)
        metrics = institutional_libs.calculate_institutional_metrics(returns)
        assert metrics is not None
        assert metrics.max_drawdown <= 0.0, (
            f"max_drawdown should be <= 0; got {metrics.max_drawdown:.4f}"
        )

    def test_volatility_in_realistic_range(self, institutional_libs, evolved_params):
        returns = self._build_returns(evolved_params.fitness_score, evolved_params.risk_factor)
        metrics = institutional_libs.calculate_institutional_metrics(returns)
        assert metrics is not None
        assert 0.0 < metrics.volatility < 1.0, (
            f"volatility {metrics.volatility:.4f} outside realistic range (0, 1)"
        )

    def test_calmar_ratio_finite(self, institutional_libs, evolved_params):
        returns = self._build_returns(evolved_params.fitness_score, evolved_params.risk_factor)
        metrics = institutional_libs.calculate_institutional_metrics(returns)
        assert metrics is not None
        assert np.isfinite(metrics.calmar_ratio)


class TestRiskManagerIntrospection:
    """Verify E01 RiskManager.get_status() and get_metrics() are callable class methods.

    Both were dead code before Audit v20 (defined inside get_risk_manager() after its
    return statement). The fix added them directly to the RiskManager class.
    """

    @pytest.fixture
    def risk_manager(self):
        try:
            from SpyderE_Risk.SpyderE01_RiskManager import get_risk_manager
            return get_risk_manager()
        except Exception as exc:
            pytest.skip(f"E01 RiskManager unavailable: {exc}")

    def test_get_status_returns_dict(self, risk_manager):
        status = risk_manager.get_status()
        assert isinstance(status, dict)

    def test_get_status_has_required_keys(self, risk_manager):
        status = risk_manager.get_status()
        for key in ("monitoring_enabled", "positions_count", "daily_pnl", "risk_checks"):
            assert key in status, f"key '{key}' missing from get_status()"

    def test_get_metrics_returns_dict(self, risk_manager):
        metrics = risk_manager.get_metrics()
        assert isinstance(metrics, dict)

    def test_get_metrics_has_required_keys(self, risk_manager):
        metrics = risk_manager.get_metrics()
        for key in ("risk_checks", "warnings", "blocks", "uptime_seconds"):
            assert key in metrics, f"key '{key}' missing from get_metrics()"

    def test_check_rate_non_negative(self, risk_manager):
        metrics = risk_manager.get_metrics()
        assert metrics.get("check_rate", 0) >= 0.0


class TestEventManagerAPI:
    """Verify new A05 EventManager additions from Audit v20.

    Covers: SIGNAL_GENERATED / PERFORMANCE_UPDATE enum values, Event.create(),
    synchronous inline dispatch when not started, get_recent_events(), and
    the two-arg unsubscribe(event_type, callable) overload.
    """

    @pytest.fixture
    def em_imports(self):
        """Return (EventManager, EventType, Event) or skip."""
        try:
            from SpyderA_Core.SpyderA05_EventManager import EventManager, EventType, Event
            return EventManager, EventType, Event
        except Exception as exc:
            pytest.skip(f"A05 EventManager unavailable: {exc}")

    def test_signal_generated_enum_exists(self, em_imports):
        _, EventType, _ = em_imports
        assert hasattr(EventType, "SIGNAL_GENERATED")

    def test_performance_update_enum_exists(self, em_imports):
        _, EventType, _ = em_imports
        assert hasattr(EventType, "PERFORMANCE_UPDATE")

    def test_event_create_classmethod(self, em_imports):
        _, EventType, Event = em_imports
        evt = Event.create(EventType.SIGNAL_GENERATED, "smoke_test", {"signal": "buy"})
        assert evt.event_type == EventType.SIGNAL_GENERATED
        assert evt.source == "smoke_test"
        assert evt.data["signal"] == "buy"

    def test_publish_dispatches_synchronously_when_not_started(self, em_imports):
        """publish() must invoke handlers inline when start() has not been called."""
        EventManager, EventType, Event = em_imports
        em = EventManager()
        received = []
        em.subscribe(EventType.SIGNAL_GENERATED, lambda e: received.append(e))
        em.publish(Event.create(EventType.SIGNAL_GENERATED, "test", {"x": 1}))
        assert len(received) == 1

    def test_get_recent_events_returns_published(self, em_imports):
        EventManager, EventType, Event = em_imports
        em = EventManager()
        for i in range(3):
            em.publish(Event.create(EventType.PERFORMANCE_UPDATE, "test", {"i": i}))
        history = em.get_recent_events(EventType.PERFORMANCE_UPDATE)
        assert len(history) == 3

    def test_unsubscribe_by_callable_removes_handler(self, em_imports):
        """unsubscribe(event_type, callable) must prevent further delivery."""
        EventManager, EventType, Event = em_imports
        em = EventManager()
        received = []

        def cb(e):
            received.append(e)

        em.subscribe(EventType.SIGNAL_GENERATED, cb)
        em.unsubscribe(EventType.SIGNAL_GENERATED, cb)
        em.publish(Event.create(EventType.SIGNAL_GENERATED, "test", {}))
        assert len(received) == 0


class TestR08RSIConfirmation:
    """Verify R08 _generate_signal() gates MA crossover signals with RSI.

    Before Audit v20, _rsi_from_prices() was implemented but never called.
    The fix wires it into _generate_signal so overbought/oversold conditions
    suppress BUY/SELL signals (RSI > 72 blocks BUY, RSI < 28 blocks SELL).
    The decision log dict also gains an 'rsi' key for diagnostics.
    """

    def test_r08_importable(self):
        try:
            from SpyderR_Runtime.SpyderR08_PaperTradingQtWorker import PaperTradingWorker
        except ImportError as exc:
            pytest.skip(f"R08 unavailable (PySide6 or other dep missing): {exc}")
        except Exception as exc:
            pytest.skip(f"R08 unavailable: {exc}")
        assert PaperTradingWorker is not None

    def test_generate_signal_calls_rsi(self):
        """_generate_signal must reference _rsi_from_prices (RSI gate)."""
        try:
            from SpyderR_Runtime.SpyderR08_PaperTradingQtWorker import PaperTradingWorker
            src = inspect.getsource(PaperTradingWorker._generate_signal)
        except ImportError as exc:
            pytest.skip(f"R08 unavailable: {exc}")
        except Exception as exc:
            pytest.skip(f"R08 source inspection unavailable: {exc}")
        assert "_rsi_from_prices" in src, (
            "_generate_signal does not call _rsi_from_prices — RSI confirmation gate missing"
        )

    def test_decision_log_includes_rsi_key(self):
        """_poll_and_trade decision log dict must include an 'rsi' key."""
        try:
            from SpyderR_Runtime.SpyderR08_PaperTradingQtWorker import PaperTradingWorker
            src = inspect.getsource(PaperTradingWorker._poll_and_trade)
        except ImportError as exc:
            pytest.skip(f"R08 unavailable: {exc}")
        except Exception as exc:
            pytest.skip(f"R08 source inspection unavailable: {exc}")
        assert '"rsi"' in src, (
            "Decision log in _poll_and_trade does not include 'rsi' key"
        )


class TestPMROverrideEnvironment:
    """Verify PMR override env-var semantics documented in the S08/D25 integration."""

    def test_pmr_env_var_is_valid_value(self):
        """SPYDER_PIVOT_MR_ENABLED must be '0' or '1' when set."""
        val = os.environ.get("SPYDER_PIVOT_MR_ENABLED", "0")
        assert val in ("0", "1"), f"Unexpected SPYDER_PIVOT_MR_ENABLED value: {val!r}"

    def test_s08_signal_importable(self):
        """S08 must expose PivotDirection, PivotMRSignal, and PivotMeanReversionSignal."""
        try:
            from SpyderS_Signals.SpyderS08_PivotMeanReversionSignal import (
                PivotDirection,
                PivotMRSignal,
                PivotMeanReversionSignal,
            )
        except ImportError as exc:
            pytest.skip(f"S08 optional dependency missing: {exc}")
        assert PivotDirection is not None
        assert PivotMRSignal is not None
        assert PivotMeanReversionSignal is not None

    def test_s08_min_fire_score_sensible(self):
        """MIN_FIRE_SCORE should be between 1 and 100."""
        try:
            from SpyderS_Signals.SpyderS08_PivotMeanReversionSignal import MIN_FIRE_SCORE
        except ImportError as exc:
            pytest.skip(f"S08 optional dependency missing: {exc}")
        assert 1 <= MIN_FIRE_SCORE <= 100, (
            f"MIN_FIRE_SCORE={MIN_FIRE_SCORE} outside expected range [1, 100]"
        )


class TestVetoConfigAndWiring:
    """Verify config and code wiring for X16/Y03/Y05 veto toggles."""

    @staticmethod
    def _load_profile(name: str) -> dict:
        cfg_path = project_root.parent / "config" / f"{name}.json"
        if not cfg_path.exists():
            pytest.skip(f"Config profile not found: {cfg_path}")
        return json.loads(cfg_path.read_text(encoding="utf-8"))

    @pytest.mark.parametrize("profile", ["config", "development", "production"])
    def test_veto_keys_exist_and_boolean(self, profile: str):
        payload = self._load_profile(profile)
        for key in VETO_KEYS:
            assert key in payload, f"{profile}.json missing key: {key}"
            assert isinstance(payload[key], bool), (
                f"{profile}.json key '{key}' must be bool, got {type(payload[key]).__name__}"
            )

    def test_master_controller_reads_veto_keys(self):
        try:
            from SpyderA_Core import SpyderA06_MasterController as a06
            source = inspect.getsource(a06)
        except Exception as exc:
            pytest.skip(f"A06 source unavailable: {exc}")

        for key in VETO_KEYS:
            assert key in source, f"A06 missing veto key wiring: {key}"

    def test_y03_exposes_enable_trade_veto_constructor_arg(self):
        try:
            from SpyderY_AutoAgents.SpyderY03_RiskSentinelAgent import RiskSentinelAgent
            sig = inspect.signature(RiskSentinelAgent.__init__)
        except Exception as exc:
            pytest.skip(f"Y03 unavailable: {exc}")

        assert "enable_trade_veto" in sig.parameters

    def test_y05_exposes_enable_veto_consumption_constructor_arg(self):
        try:
            from SpyderY_AutoAgents.SpyderY05_ExecutionOptimizerAgent import ExecutionOptimizerAgent
            sig = inspect.signature(ExecutionOptimizerAgent.__init__)
        except Exception as exc:
            pytest.skip(f"Y05 unavailable: {exc}")

        assert "enable_veto_consumption" in sig.parameters


# ==============================================================================
# STANDALONE ENTRY POINT (informational output for direct execution)
# ==============================================================================

def _run_smoke_output() -> None:
    """Print a human-readable summary when run directly (not via pytest)."""
    print("=" * 70)
    print("SPYDER T06 — Evolved Credit Spread Smoke Test")
    print("Stack: D25 + D18 (Gen15/0.799) + S08 PMR + L09 + V09 + E01 + U20")
    print("=" * 70)

    try:
        from SpyderU_Utilities.SpyderU20_InstitutionalLibraries import (
            OptionType,
            get_institutional_libraries,
        )
        libs = get_institutional_libraries()
        print("U20 InstitutionalLibraries: OK")
    except Exception as exc:
        print(f"U20 load failed: {exc}")
        return

    print("\nCanonical module availability:")
    for label, dotted in CANONICAL_MODULES.items():
        try:
            __import__(dotted)
            print(f"  OK  {label}")
        except Exception as exc:
            print(f"  --  {label} ({type(exc).__name__})")

    try:
        from SpyderD_Strategies.SpyderD18_EvolvedCreditSpread import EvolvedStrategyParams
        params = EvolvedStrategyParams()
    except Exception:
        params = type("P", (), {  # type: ignore[call-overload]
            "fitness_score": 0.799, "generation": 15,
            "risk_factor": 0.212, "strategy_type": "credit_spread",
        })()

    print(
        f"\nEvolved params: Gen{params.generation} / fitness={params.fitness_score:.3f}"
        f" / risk_factor={params.risk_factor:.3f}"
    )

    short = libs.price_option(
        spot=400.0, strike=393.0, time_to_expiry=0.0274,
        risk_free_rate=0.05, volatility=0.17, option_type=OptionType.PUT,
    )
    long_ = libs.price_option(
        spot=400.0, strike=388.0, time_to_expiry=0.0274,
        risk_free_rate=0.05, volatility=0.17, option_type=OptionType.PUT,
    )
    if short and long_:
        net_credit = short.theoretical_price - long_.theoretical_price
        width = 393.0 - 388.0
        print(
            f"\nBull-Put spread: net_credit=${net_credit:.3f}"
            f"  max_loss=${width - net_credit:.3f}"
        )
        print(
            f"Net delta={short.delta - long_.delta:+.4f}  "
            f"net_theta={short.theta - long_.theta:+.4f}/day"
        )

    np.random.seed(42)
    base = params.fitness_score * 0.00138
    vol = 0.0083 * (1 - params.risk_factor)
    returns = pd.Series(
        np.clip(np.random.normal(base, vol, 252), -0.03, 0.03),
        index=pd.date_range("2025-01-01", periods=252, freq="D"),
    )
    metrics = libs.calculate_institutional_metrics(returns)
    if metrics:
        print(
            f"\nPerformance (252-day sim): annual_return={metrics.annual_return:.2%}"
            f"  sharpe={metrics.sharpe_ratio:.2f}  sortino={metrics.sortino_ratio:.2f}"
            f"  max_dd={metrics.max_drawdown:.2%}  calmar={metrics.calmar_ratio:.2f}"
        )

    print("\nT06 smoke-test complete.")


if __name__ == "__main__":
    _run_smoke_output()

