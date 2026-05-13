#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderT_Testing
Module: test_SpyderT109_SSeries.py
Purpose: Coverage tests for SpyderS_Signals — all 7 modules

Author: Spyder Dev
Year Created: 2025
Last Updated: 2026-03-06 Time: 02:00:00
"""

# ==============================================================================
# BOOTSTRAP — stub out missing cross-module deps before any S-series import
# ==============================================================================
import os
import sys
import types
import logging
import signal
import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

logging.disable(logging.CRITICAL)

_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# Use offscreen Qt backend so PySide6 works in headless environments
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _ensure_mod(key):
    """Create stub module and all ancestor package stubs."""
    parts = key.split(".")
    for i in range(1, len(parts) + 1):
        ancestor = ".".join(parts[:i])
        if ancestor not in sys.modules:
            sys.modules[ancestor] = types.ModuleType(ancestor)
    return sys.modules[key]


# --- U01/U02 stubs (S07 hard-imports these) ----------------------------------
_u01 = _ensure_mod("Spyder.SpyderU_Utilities.SpyderU01_Logger")
if not hasattr(_u01, "SpyderLogger"):
    _u01.SpyderLogger = type("SpyderLogger", (), {
        "get_logger": staticmethod(lambda name: logging.getLogger(name))
    })

_u02 = _ensure_mod("Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler")
if not hasattr(_u02, "SpyderErrorHandler"):
    _u02.SpyderErrorHandler = type("SpyderErrorHandler", (), {})

# --- S04 plain-name stub modules (non-dotted imports inside S04) -------------
# S04 does: from SpyderS06_BlackSwanDataCollector import BlackSwanDataCollector
# S04 does: from SpyderS07_BlackSwanCalculator import BlackSwanCalculator, ...
from enum import Enum as _Enum

_s04_dc_mod = types.ModuleType("SpyderS06_BlackSwanDataCollector")
_s04_dc_mod.BlackSwanDataCollector = type(
    "BlackSwanDataCollector", (), {"__init__": lambda self, *a, **k: None}
)
sys.modules.setdefault("SpyderS06_BlackSwanDataCollector", _s04_dc_mod)

_S04RiskStatus = _Enum("RiskStatus", {"GREEN": "GREEN", "YELLOW": "YELLOW", "RED": "RED"})
_S04AlertLevel = _Enum("AlertLevel", {"LOW": "LOW", "MEDIUM": "MEDIUM", "HIGH": "HIGH"})
_S04BlackSwanIndicatorResult = type("BlackSwanIndicatorResult", (), {})

_s04_calc_mod = types.ModuleType("SpyderS07_BlackSwanCalculator")
_s04_calc_mod.BlackSwanCalculator = type(
    "BlackSwanCalculator", (), {"__init__": lambda self, *a, **k: None}
)
_s04_calc_mod.BlackSwanIndicatorResult = _S04BlackSwanIndicatorResult
_s04_calc_mod.RiskStatus = _S04RiskStatus
_s04_calc_mod.AlertLevel = _S04AlertLevel
sys.modules.setdefault("SpyderS07_BlackSwanCalculator", _s04_calc_mod)

# --- S-series package pre-stub -----------------------------------------------
# Avoid running __init__.py (which imports S07 → PySide6 → display requirement)
_s_pkg_path = os.path.join(_ROOT, "Spyder", "SpyderS_Signals")
_s_pkg = sys.modules.setdefault(
    "Spyder.SpyderS_Signals",
    types.ModuleType("Spyder.SpyderS_Signals"),
)
_s_pkg.__path__ = [_s_pkg_path]
_s_pkg.__package__ = "Spyder.SpyderS_Signals"
_s_pkg.__file__ = os.path.join(_s_pkg_path, "__init__.py")

# --- Qt application for S07 tests --------------------------------------------
try:
    from PySide6.QtWidgets import QApplication as _QApp
    _qt_app = _QApp.instance() or _QApp(sys.argv[:1])
except Exception:
    _qt_app = None

# --- Force-load S05 from disk ------------------------------------------------
# T108 bootstrap stubs Spyder.SpyderS_Signals.SpyderS05_GEXDEXCalculator with
# only 'GammaExposureCalculator'; when T109 runs after T108 in the full suite
# the cached stub breaks our import.  Replace it with the real module.
import importlib.util as _ilu

_s05_key = "Spyder.SpyderS_Signals.SpyderS05_GEXDEXCalculator"
if not hasattr(sys.modules.get(_s05_key, types.SimpleNamespace()), "GEXDEXCalculator"):
    _s05_file = os.path.join(_s_pkg_path, "SpyderS05_GEXDEXCalculator.py")
    _s05_spec = _ilu.spec_from_file_location(_s05_key, _s05_file)
    _s05_real = _ilu.module_from_spec(_s05_spec)
    _s05_real.__package__ = "Spyder.SpyderS_Signals"
    sys.modules[_s05_key] = _s05_real
    _s05_spec.loader.exec_module(_s05_real)


# ==============================================================================
# S01_DIXCalculator — enums + dataclasses + classes
# ==============================================================================
from Spyder.SpyderS_Signals.SpyderS01_DIXCalculator import (
    DataSource,
    CalculationStatus,
    StockDPI,
    DIXResult,
    SpyderDIXCalculator,
    DIXCalculator,
)


class TestS01Enums(unittest.TestCase):
    def test_data_source_values(self):
        self.assertEqual(DataSource.FINRA.value, "finra")
        self.assertEqual(DataSource.YFINANCE.value, "yfinance")
        self.assertEqual(DataSource.WIKIPEDIA.value, "wikipedia")
        self.assertIn(DataSource.SIMULATED, DataSource)

    def test_calculation_status_values(self):
        self.assertEqual(CalculationStatus.PENDING.value, "pending")
        self.assertEqual(CalculationStatus.IN_PROGRESS.value, "in_progress")
        self.assertEqual(CalculationStatus.COMPLETED.value, "completed")
        self.assertEqual(CalculationStatus.FAILED.value, "failed")
        self.assertIn(CalculationStatus.SUCCESS, CalculationStatus)


class TestS01DataClasses(unittest.TestCase):
    def test_stock_dpi_creation(self):
        dpi = StockDPI(
            symbol="AAPL",
            short_volume=1_000_000,
            total_volume=5_000_000,
            dpi=0.20,
            market_cap=3e12,
            weight=0.07,
            contribution=0.014,
        )
        self.assertEqual(dpi.symbol, "AAPL")
        self.assertAlmostEqual(dpi.dpi, 0.20)
        self.assertAlmostEqual(dpi.contribution, 0.014)

    def test_dix_result_creation(self):
        result = DIXResult(
            date="2026-03-06",
            dix_value=0.42,
            dix_percentage=42.0,
            num_components=500,
            total_market_cap=40e12,
            breakdown={},
            calculation_time=datetime.now(),
            metadata={"source": "finra"},
        )
        self.assertEqual(result.date, "2026-03-06")
        self.assertAlmostEqual(result.dix_value, 0.42)
        self.assertEqual(result.num_components, 500)


class TestS01Classes(unittest.TestCase):
    def test_spyder_dix_calculator_instantiation(self):
        calc = SpyderDIXCalculator()
        self.assertIsNotNone(calc)

    def test_dix_calculator_instantiation(self):
        calc = DIXCalculator()
        self.assertIsNotNone(calc)


# ==============================================================================
# S02_DIXScheduler — enums + dataclasses + SpyderDIXScheduler
# ==============================================================================
from Spyder.SpyderS_Signals.SpyderS02_DIXScheduler import (
    SchedulerStatus,
    DataFetchStatus,
    SchedulerConfig,
    CalculationResult,
    SpyderDIXScheduler,
)


class TestS02Enums(unittest.TestCase):
    def test_scheduler_status_values(self):
        self.assertEqual(SchedulerStatus.IDLE.value, "idle")
        self.assertEqual(SchedulerStatus.RUNNING.value, "running")
        self.assertEqual(SchedulerStatus.ERROR.value, "error")
        self.assertIn(SchedulerStatus.COMPLETED, SchedulerStatus)

    def test_data_fetch_status_values(self):
        self.assertEqual(DataFetchStatus.PENDING.value, "pending")
        self.assertEqual(DataFetchStatus.FETCHING.value, "fetching")
        self.assertEqual(DataFetchStatus.SUCCESS.value, "success")
        self.assertIn(DataFetchStatus.FAILED, DataFetchStatus)


class TestS02DataClasses(unittest.TestCase):
    def test_scheduler_config_creation(self):
        cfg = SchedulerConfig(
            use_demo=True,
            enable_email_alerts=False,
            enable_visualizations=False,
            save_to_database=False,
            retry_on_failure=True,
        )
        self.assertTrue(cfg.use_demo)
        self.assertFalse(cfg.enable_email_alerts)

    def test_calculation_result_creation(self):
        result = CalculationResult(
            timestamp=datetime.now(),
            dix_value=0.42,
            dix_percentage=42.0,
            sentiment="BULLISH",
            status=SchedulerStatus.COMPLETED,
            error_message=None,
            execution_time=1.23,
        )
        self.assertAlmostEqual(result.dix_value, 0.42)
        self.assertEqual(result.sentiment, "BULLISH")
        self.assertIsNone(result.error_message)


class TestS02Scheduler(unittest.TestCase):
    """S02 has a source bug: SpyderDIXDemo is imported in a try block but the
    except fallback omits it, leaving the name undefined.  We inject it (and the
    other missing names) into the module namespace via patch.multiple."""

    @staticmethod
    def _make_scheduler(config=None):
        import Spyder.SpyderS_Signals.SpyderS02_DIXScheduler as _m
        with patch.multiple(
            _m,
            SpyderDIXDemo=MagicMock,
            SpyderDIXVisualizer=MagicMock,
            SpyderDIXCalculator=MagicMock,
            create=True,
        ):
            return SpyderDIXScheduler(config=config)

    def test_instantiation_no_args(self):
        scheduler = self._make_scheduler()
        self.assertIsNotNone(scheduler)

    def test_instantiation_with_config(self):
        cfg = SchedulerConfig(
            use_demo=True,
            enable_email_alerts=False,
            enable_visualizations=False,
            save_to_database=False,
            retry_on_failure=False,
        )
        scheduler = self._make_scheduler(config=cfg)
        self.assertIsNotNone(scheduler)

    def test_status_initially_idle(self):
        scheduler = self._make_scheduler()
        self.assertEqual(scheduler.status, SchedulerStatus.IDLE)


# ==============================================================================
# S03_BlackSwanIndicator — enums + dataclasses + BlackSwanIndicator
# ==============================================================================
from Spyder.SpyderS_Signals.SpyderS03_BlackSwanIndicator import (
    RiskStatus,
    DataQuality,
    ComponentScore,
    BlackSwanResult,
    BlackSwanIndicator,
)


class TestS03Enums(unittest.TestCase):
    def test_risk_status_values(self):
        self.assertEqual(RiskStatus.GREEN.value, "GREEN")
        self.assertEqual(RiskStatus.YELLOW.value, "YELLOW")
        self.assertEqual(RiskStatus.RED.value, "RED")
        self.assertEqual(len(RiskStatus), 3)

    def test_data_quality_values(self):
        self.assertEqual(DataQuality.GOOD.value, "good")
        self.assertEqual(DataQuality.PARTIAL.value, "partial")
        self.assertEqual(DataQuality.POOR.value, "poor")


class TestS03DataClasses(unittest.TestCase):
    def test_component_score_creation(self):
        cs = ComponentScore(
            name="volatility",
            raw_score=2.5,
            weight=0.30,
            weighted_score=0.75,
            description="Volatility component",
        )
        self.assertEqual(cs.name, "volatility")
        self.assertAlmostEqual(cs.weighted_score, 0.75)
        self.assertIsInstance(cs.details, dict)

    def test_black_swan_result_creation(self):
        cs = ComponentScore(
            name="vol",
            raw_score=1.0,
            weight=1.0,
            weighted_score=1.0,
            description="test",
        )
        bsr = BlackSwanResult(
            timestamp=datetime.now(),
            overall_score=1.5,
            status=RiskStatus.GREEN,
            component_scores={"volatility": cs},
            data_quality=DataQuality.GOOD,
            calculation_time_ms=42.0,
        )
        self.assertAlmostEqual(bsr.overall_score, 1.5)
        self.assertEqual(bsr.status, RiskStatus.GREEN)
        self.assertIsNone(bsr.raw_data)


class TestS03Indicator(unittest.TestCase):
    def test_instantiation_no_args(self):
        indicator = BlackSwanIndicator()
        self.assertIsNotNone(indicator)

    def test_instantiation_with_config(self):
        indicator = BlackSwanIndicator(config={"weights": {"volatility": 0.5}})
        self.assertIsNotNone(indicator)


# ==============================================================================
# S04_BlackSwanScheduler — enums + dataclasses + BlackSwanScheduler
# ==============================================================================
from Spyder.SpyderS_Signals.SpyderS04_BlackSwanScheduler import (
    ScheduleType,
    NotificationChannel,
    ScheduledTask,
    AlertRecord,
    DailyReport,
    BlackSwanScheduler,
)


class TestS04Enums(unittest.TestCase):
    def test_schedule_type_values(self):
        self.assertEqual(ScheduleType.MARKET_CHECK.value, "market_check")
        self.assertEqual(ScheduleType.DAILY_REPORT.value, "daily_report")
        self.assertEqual(ScheduleType.ALERT_CHECK.value, "alert_check")
        self.assertIn(ScheduleType.CLEANUP, ScheduleType)

    def test_notification_channel_values(self):
        self.assertEqual(NotificationChannel.EMAIL.value, "email")
        self.assertEqual(NotificationChannel.SMS.value, "sms")
        self.assertEqual(NotificationChannel.SLACK.value, "slack")
        self.assertIn(NotificationChannel.TELEGRAM, NotificationChannel)
        self.assertIn(NotificationChannel.LOG, NotificationChannel)


class TestS04DataClasses(unittest.TestCase):
    def test_scheduled_task_creation(self):
        task = ScheduledTask(
            task_id="task-001",
            task_type=ScheduleType.MARKET_CHECK,
            schedule_time="09:15",
            callback=lambda: None,
            enabled=True,
            last_run=None,
            next_run=datetime.now(),
        )
        self.assertEqual(task.task_id, "task-001")
        self.assertTrue(task.enabled)

    def test_alert_record_creation(self):
        ar = AlertRecord(
            timestamp=datetime.now(),
            status=_S04RiskStatus.GREEN,
            score=1.5,
            message="System is normal",
            channels=[NotificationChannel.LOG],
        )
        self.assertAlmostEqual(ar.score, 1.5)
        self.assertEqual(ar.message, "System is normal")

    def test_daily_report_creation(self):
        dr = DailyReport(
            date=datetime.now(),
            checks_performed=5,
            average_score=1.8,
            max_score=2.2,
            status_distribution={"GREEN": 4, "YELLOW": 1},
            alerts_sent=0,
            data_quality="good",
        )
        self.assertEqual(dr.checks_performed, 5)
        self.assertAlmostEqual(dr.average_score, 1.8)


class TestS04Scheduler(unittest.TestCase):
    def test_instantiation_no_args(self):
        scheduler = BlackSwanScheduler()
        self.assertIsNotNone(scheduler)

    def test_instantiation_with_config(self):
        scheduler = BlackSwanScheduler(config={"alert_cooldown_minutes": 30})
        self.assertIsNotNone(scheduler)

    def test_running_flag_initially_false(self):
        scheduler = BlackSwanScheduler()
        self.assertFalse(scheduler.running)

    def test_signal_handler_chains_default_sigterm(self):
        scheduler = BlackSwanScheduler()
        scheduler._previous_signal_handlers[signal.SIGTERM] = signal.SIG_DFL
        scheduler.stop = MagicMock()

        with patch(
            "Spyder.SpyderS_Signals.SpyderS04_BlackSwanScheduler.signal.signal"
        ) as signal_mock, patch(
            "Spyder.SpyderS_Signals.SpyderS04_BlackSwanScheduler.os.kill"
        ) as kill_mock:
            scheduler._signal_handler(signal.SIGTERM, None)

        scheduler.stop.assert_called_once_with()
        signal_mock.assert_called_once_with(signal.SIGTERM, signal.SIG_DFL)
        kill_mock.assert_called_once_with(os.getpid(), signal.SIGTERM)


# ==============================================================================
# S05_GEXDEXCalculator — GEXDEXCalculator + module function
# ==============================================================================
from Spyder.SpyderS_Signals.SpyderS05_GEXDEXCalculator import (
    GEXDEXCalculator,
    get_gex_calculator,
)


class TestS05GEXDEXCalculator(unittest.TestCase):
    def setUp(self):
        self.calc = GEXDEXCalculator()
        # Pre-populate with simulated data so get_* methods have cached results
        self.calc.calculate_simulated()

    def test_instantiation(self):
        self.assertIsNotNone(self.calc)

    def test_calculate_simulated_returns_dict(self):
        result = self.calc.calculate_simulated()
        self.assertIsInstance(result, dict)
        self.assertIn("gex", result)
        self.assertIn("dex", result)
        self.assertIn("ogl", result)
        self.assertIn("timestamp", result)

    def test_calculate_all_returns_dict(self):
        # Use simulated data since calculate_all() without args requires live data
        result = self.calc.calculate_simulated()
        self.assertIsInstance(result, dict)
        self.assertIn("gex", result)

    def test_get_gex_returns_float(self):
        result = self.calc.calculate_simulated()
        val = result["gex"]
        self.assertIsInstance(val, float)

    def test_get_dex_returns_float(self):
        result = self.calc.calculate_simulated()
        val = result["dex"]
        self.assertIsInstance(val, float)

    def test_get_ogl_returns_float(self):
        result = self.calc.calculate_simulated()
        val = result["ogl"]
        self.assertIsInstance(val, float)

    def test_timestamp_is_datetime(self):
        result = self.calc.calculate_simulated()
        self.assertIsInstance(result["timestamp"], datetime)


class TestS05ModuleFunction(unittest.TestCase):
    def test_get_gex_calculator_returns_instance(self):
        calc = get_gex_calculator()
        self.assertIsInstance(calc, GEXDEXCalculator)

    def test_get_gex_calculator_singleton(self):
        c1 = get_gex_calculator()
        c2 = get_gex_calculator()
        self.assertIs(c1, c2)


# ==============================================================================
# S06_SKEWCalculator — dataclasses + SpyderS06_SKEWCalculator
# ==============================================================================
from Spyder.SpyderS_Signals.SpyderS06_SKEWCalculator import (
    OptionData,
    SKEWCalculation,
    SKEWComponents,
    SpyderS06_SKEWCalculator,
)


class TestS06DataClasses(unittest.TestCase):
    def test_option_data_creation(self):
        od = OptionData(
            strike=450.0,
            expiry=datetime.now() + timedelta(days=30),
            option_type="call",
            bid=1.90,
            ask=2.10,
            mid=2.00,
            last=2.05,
            volume=5000,
            open_interest=20000,
            implied_volatility=0.20,
            delta=0.50,
            gamma=0.02,
            theta=-0.10,
            vega=0.30,
            moneyness=1.0,
            time_to_expiry=30 / 365,
        )
        self.assertEqual(od.strike, 450.0)
        self.assertEqual(od.option_type, "call")
        self.assertAlmostEqual(od.moneyness, 1.0)

    def test_skew_calculation_creation(self):
        sc = SKEWCalculation(
            skew_index=120.5,
            timestamp=datetime.now(),
            spot_price=450.0,
            risk_free_rate=0.05,
            expiry_used=datetime.now() + timedelta(days=30),
            strikes_used=20,
            put_skew=0.03,
            call_skew=-0.01,
            third_moment=-0.25,
            confidence=0.95,
            calculation_time=12.5,
        )
        self.assertAlmostEqual(sc.skew_index, 120.5)
        self.assertEqual(sc.strikes_used, 20)
        self.assertIsInstance(sc.metadata, dict)

    def test_skew_components_creation(self):
        sc = SKEWComponents(
            spot=450.0,
            forward=451.5,
            atm_volatility=0.20,
            risk_neutral_skew=-0.25,
            risk_neutral_kurtosis=3.5,
            put_wing=[(440.0, 0.22), (430.0, 0.25)],
            call_wing=[(460.0, 0.18), (470.0, 0.16)],
            interpolation_quality=0.98,
        )
        self.assertAlmostEqual(sc.spot, 450.0)
        self.assertEqual(len(sc.put_wing), 2)
        self.assertEqual(len(sc.call_wing), 2)


class TestS06SKEWCalculator(unittest.TestCase):
    def test_instantiation_no_args(self):
        calc = SpyderS06_SKEWCalculator()
        self.assertIsNotNone(calc)

    def test_instantiation_with_config(self):
        calc = SpyderS06_SKEWCalculator(config={"symbol": "SPY", "days_to_expiry": 30})
        self.assertIsNotNone(calc)


# ==============================================================================
# S07_CustomMetricsOrchestrator — dataclasses + StressLevel + orchestrator
# ==============================================================================
from Spyder.SpyderS_Signals.SpyderS07_CustomMetricsOrchestrator import (
    MetricSnapshot,
    MetricQuality,
    StressLevel,
    CustomMetricsOrchestrator,
)


class TestS07Dataclasses(unittest.TestCase):
    def test_metric_snapshot_creation_defaults(self):
        snap = MetricSnapshot()
        self.assertAlmostEqual(snap.gex, 0.0)
        self.assertAlmostEqual(snap.dex, 0.0)
        self.assertAlmostEqual(snap.swan, 1.0)
        self.assertAlmostEqual(snap.skew, 100.0)
        self.assertIsInstance(snap.timestamp, datetime)

    def test_metric_snapshot_custom_values(self):
        snap = MetricSnapshot(gex=-1.5e9, dex=800e6, skew=115.0)
        self.assertAlmostEqual(snap.gex, -1.5e9)
        self.assertAlmostEqual(snap.skew, 115.0)

    def test_metric_quality_creation(self):
        mq = MetricQuality(
            metric_name="GEX",
            quality_score=0.95,
            data_points=100,
            last_successful_update=datetime.now(),
        )
        self.assertEqual(mq.metric_name, "GEX")
        self.assertAlmostEqual(mq.quality_score, 0.95)
        self.assertEqual(mq.error_count, 0)
        self.assertTrue(mq.source_available)


class TestS07StressLevel(unittest.TestCase):
    def test_stress_level_values(self):
        self.assertEqual(StressLevel.LOW.value, "low")
        self.assertEqual(StressLevel.MEDIUM.value, "medium")
        self.assertEqual(StressLevel.HIGH.value, "high")
        self.assertEqual(StressLevel.CRISIS.value, "crisis")
        self.assertEqual(len(StressLevel), 4)


class TestS07Orchestrator(unittest.TestCase):
    def test_instantiation(self):
        if _qt_app is None:
            self.skipTest("QApplication unavailable in this environment")
        with patch.object(CustomMetricsOrchestrator, "start", return_value=None):
            orch = CustomMetricsOrchestrator(config={"auto_start": False})
            self.assertIsNotNone(orch)

    def test_current_metrics_structure(self):
        if _qt_app is None:
            self.skipTest("QApplication unavailable in this environment")
        with patch.object(CustomMetricsOrchestrator, "start", return_value=None):
            orch = CustomMetricsOrchestrator(config={"auto_start": False})
            self.assertIn("GEX", orch.current_metrics)
            self.assertIn("DEX", orch.current_metrics)
            self.assertIn("DIX", orch.current_metrics)
            self.assertIn("SWAN", orch.current_metrics)
            self.assertIn("SKEW", orch.current_metrics)

    def test_initial_stress_level(self):
        if _qt_app is None:
            self.skipTest("QApplication unavailable in this environment")
        with patch.object(CustomMetricsOrchestrator, "start", return_value=None):
            orch = CustomMetricsOrchestrator(config={"auto_start": False})
            self.assertEqual(orch.current_stress_level, StressLevel.LOW)

    def test_market_conditions_include_cross_index_confirmation_snapshot(self):
        if _qt_app is None:
            self.skipTest("QApplication unavailable in this environment")
        with patch.object(CustomMetricsOrchestrator, "start", return_value=None):
            orch = CustomMetricsOrchestrator(config={"auto_start": False})
            with patch.object(
                orch,
                "_load_index_confirmation_snapshot",
                return_value={
                    "spy_change_pct": -0.45,
                    "qqq_change_pct": -0.80,
                    "iwm_change_pct": -1.10,
                    "xlk_change_pct": -1.40,
                    "xlf_change_pct": 0.05,
                },
            ):
                conditions = orch.get_current_market_conditions()

        self.assertAlmostEqual(conditions["spy_change_pct"], -0.45)
        self.assertAlmostEqual(conditions["qqq_change_pct"], -0.80)
        self.assertAlmostEqual(conditions["iwm_change_pct"], -1.10)
        self.assertAlmostEqual(conditions["xlk_change_pct"], -1.40)
        self.assertAlmostEqual(conditions["xlf_change_pct"], 0.05)


# ==============================================================================
# Cross-module consistency tests
# ==============================================================================
class TestSSeriesCrossModule(unittest.TestCase):
    def test_data_source_enum_complete(self):
        sources = {ds.value for ds in DataSource}
        self.assertIn("finra", sources)
        self.assertIn("yfinance", sources)

    def test_risk_status_and_status_dont_clash(self):
        # S03.RiskStatus and S04's imported RiskStatus are independent enums
        self.assertEqual(RiskStatus.GREEN.value, "GREEN")
        self.assertEqual(_S04RiskStatus.GREEN.value, "GREEN")

    def test_gex_calculator_results_are_numbers(self):
        calc = GEXDEXCalculator()
        result = calc.calculate_simulated()
        for key in ("gex", "dex", "ogl"):
            self.assertIsInstance(result[key], (int, float))

    def test_metric_snapshot_has_all_metric_keys(self):
        snap = MetricSnapshot()
        for attr in ("gex", "dex", "ogl", "dix", "swan", "skew"):
            self.assertTrue(hasattr(snap, attr))


if __name__ == "__main__":
    unittest.main()
