#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderT_Testing
Module: SpyderT54_StartupConfigValidation_Test.py
Purpose: Tests for fail-fast startup configuration validation (item #8 hardening)

Author: Mohamed Talib
Year Created: 2025
Last Updated: 2026-03-03 Time: 00:00:00

Module Description:
    Validates that ConfigurationError is raised with a complete list of ALL
    missing / invalid environment variables when validate_startup_config() is
    called, so the operator can fix every problem in one restart cycle.

    Coverage areas:
        - ConfigurationError exception hierarchy
        - validate_startup_config() — individual missing vars
        - validate_startup_config() — multi-error aggregation
        - validate_startup_config() — live-mode gate
        - validate_startup_config() — success paths (sandbox / paper / live)
        - validate_config() backward-compat (still returns bool, str)
        - SpyderA03_Configuration HAS_STARTUP_VALIDATOR flag is importable
        - ConfigManager._validate_configuration() propagates ConfigurationError

Change Log:
    2026-03-03:
        - Created (item #8 — startup config validation fail-fast)
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import importlib
import importlib.util
import os
import sys
import unittest
from contextlib import contextmanager
from pathlib import Path
from collections.abc import Iterator
from unittest.mock import MagicMock, patch

# ==============================================================================
# PATH SETUP  (mirrors other T5x tests in the suite)
# ==============================================================================
_REPO_ROOT = Path(__file__).resolve().parents[2]  # /home/.../Spyder
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# Load the config module via its filesystem path so it works regardless of
# whether 'config' is on sys.path as a package.
# Wrap with a load_dotenv no-op so we do *not* populate os.environ from .env
# at pytest-collection time (which would break skip conditions in T42).
_CONFIG_PATH = _REPO_ROOT / "config" / "config.py"
with patch("dotenv.load_dotenv"):
    _spec = importlib.util.spec_from_file_location("_spyder_config_t54", _CONFIG_PATH)
    _cfg_mod = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
    _spec.loader.exec_module(_cfg_mod)  # type: ignore[union-attr]

# Pull key names into module scope for brevity
ConfigurationError = _cfg_mod.ConfigurationError
validate_startup_config = _cfg_mod.validate_startup_config
validate_config = _cfg_mod.validate_config


# ==============================================================================
# HELPERS
# ==============================================================================

# Minimal "all-good" env state for sandbox mode
_VALID_SANDBOX_ENV = {
    "TRADIER_API_KEY": "test-key-abc",
    "TRADIER_ACCOUNT_ID": "123456",
    "TRADING_MODE": "sandbox",
    "TRADIER_ENVIRONMENT": "sandbox",
    "DATA_PROVIDER": "massive",
    "MASSIVE_API_KEY": "massive-key-xyz",
    "LIVE_TRADING_CONFIRMED": "false",
}


@contextmanager
def _patched_module(env_overrides: dict) -> Iterator[None]:
    """
    Temporarily patch config module-level variables to reflect `env_overrides`
    and restore them afterwards.  This avoids reloading the module for every
    test (which would fight with load_dotenv side-effects).
    """
    # Save original values
    orig_tradier = dict(_cfg_mod.TRADIER_CONFIG)
    orig_massive = dict(_cfg_mod.MASSIVE_CONFIG)
    orig_provider = _cfg_mod.DATA_PROVIDER

    # Apply env-driven state to module-level dicts
    _cfg_mod.TRADIER_CONFIG["api_key"] = env_overrides.get("TRADIER_API_KEY", "")
    _cfg_mod.TRADIER_CONFIG["account_id"] = env_overrides.get("TRADIER_ACCOUNT_ID", "")
    provider = env_overrides.get("DATA_PROVIDER", "massive")
    _cfg_mod.DATA_PROVIDER = provider
    _cfg_mod.MASSIVE_CONFIG["api_key"] = env_overrides.get("MASSIVE_API_KEY", "")

    with patch.dict(os.environ, env_overrides, clear=False):
        try:
            yield
        finally:
            _cfg_mod.TRADIER_CONFIG.update(orig_tradier)
            _cfg_mod.MASSIVE_CONFIG.update(orig_massive)
            _cfg_mod.DATA_PROVIDER = orig_provider


# ==============================================================================
# TEST CLASSES
# ==============================================================================


class TestConfigurationErrorClass(unittest.TestCase):
    """ConfigurationError must be a RuntimeError subclass."""

    def test_is_runtime_error_subclass(self):
        self.assertTrue(issubclass(ConfigurationError, RuntimeError))

    def test_is_exception_subclass(self):
        self.assertTrue(issubclass(ConfigurationError, Exception))

    def test_can_be_raised_and_caught_as_runtime_error(self):
        with self.assertRaises(RuntimeError):
            raise ConfigurationError("something missing")

    def test_message_preserved(self):
        msg = "TRADIER_API_KEY is not set"
        exc = ConfigurationError(msg)
        self.assertIn(msg, str(exc))


class TestValidateStartupConfigSuccess(unittest.TestCase):
    """validate_startup_config() must NOT raise when all vars are present."""

    def test_sandbox_mode_all_vars_present(self):
        with _patched_module(_VALID_SANDBOX_ENV):
            # Should complete without raising
            validate_startup_config()

    def test_paper_mode_all_vars_present(self):
        env = {**_VALID_SANDBOX_ENV, "TRADING_MODE": "paper"}
        with _patched_module(env):
            validate_startup_config()

    def test_live_mode_with_confirmation(self):
        env = {
            **_VALID_SANDBOX_ENV,
            "TRADING_MODE": "live",
            "LIVE_TRADING_CONFIRMED": "true",
        }
        with _patched_module(env):
            validate_startup_config()

    def test_massive_provider_with_key(self):
        env = {
            **_VALID_SANDBOX_ENV,
            "DATA_PROVIDER": "massive",
            "MASSIVE_API_KEY": "massive-key-123",
        }
        with _patched_module(env):
            validate_startup_config()


class TestValidateStartupConfigMissingTradierApiKey(unittest.TestCase):
    """Missing TRADIER_API_KEY must appear in the error."""

    def test_raises_configuration_error(self):
        env = {**_VALID_SANDBOX_ENV, "TRADIER_API_KEY": ""}
        with _patched_module(env), self.assertRaises(ConfigurationError):
            validate_startup_config()

    def test_error_mentions_tradier_api_key(self):
        env = {**_VALID_SANDBOX_ENV, "TRADIER_API_KEY": ""}
        with _patched_module(env), self.assertRaises(ConfigurationError) as ctx:
            validate_startup_config()
        self.assertIn("TRADIER_API_KEY", str(ctx.exception))


class TestValidateStartupConfigMissingTradierAccountId(unittest.TestCase):
    """Missing TRADIER_ACCOUNT_ID must appear in the error."""

    def test_raises_configuration_error(self):
        env = {**_VALID_SANDBOX_ENV, "TRADIER_ACCOUNT_ID": ""}
        with _patched_module(env), self.assertRaises(ConfigurationError):
            validate_startup_config()

    def test_error_mentions_tradier_account_id(self):
        env = {**_VALID_SANDBOX_ENV, "TRADIER_ACCOUNT_ID": ""}
        with _patched_module(env), self.assertRaises(ConfigurationError) as ctx:
            validate_startup_config()
        self.assertIn("TRADIER_ACCOUNT_ID", str(ctx.exception))


class TestValidateStartupConfigInvalidMode(unittest.TestCase):
    """Invalid TRADING_MODE must be rejected."""

    def test_empty_mode_raises(self):
        env = {**_VALID_SANDBOX_ENV, "TRADING_MODE": ""}
        with _patched_module(env), self.assertRaises(ConfigurationError):
            validate_startup_config()

    def test_typo_mode_raises(self):
        env = {**_VALID_SANDBOX_ENV, "TRADING_MODE": "Live"}  # wrong case
        with _patched_module(env), self.assertRaises(ConfigurationError):
            validate_startup_config()

    def test_unknown_mode_error_mentions_value(self):
        env = {**_VALID_SANDBOX_ENV, "TRADING_MODE": "production"}
        with _patched_module(env), self.assertRaises(ConfigurationError) as ctx:
            validate_startup_config()
        self.assertIn("production", str(ctx.exception))

    def test_valid_modes_accepted(self):
        for mode in ("sandbox", "paper"):
            env = {**_VALID_SANDBOX_ENV, "TRADING_MODE": mode}
            with _patched_module(env):
                validate_startup_config()  # must not raise


class TestValidateStartupConfigDataProvider(unittest.TestCase):
    """Missing data-provider key must be caught."""

    def test_missing_massive_key_raises(self):
        env = {**_VALID_SANDBOX_ENV, "MASSIVE_API_KEY": "", "DATA_PROVIDER": "massive"}
        with _patched_module(env), self.assertRaises(ConfigurationError) as ctx:
            validate_startup_config()
        self.assertIn("MASSIVE_API_KEY", str(ctx.exception))

    def test_polygon_alias_is_accepted(self):
        env = {**_VALID_SANDBOX_ENV, "DATA_PROVIDER": "polygon"}
        with _patched_module(env):
            validate_startup_config()

    def test_unknown_provider_raises(self):
        env = {**_VALID_SANDBOX_ENV, "DATA_PROVIDER": "quandl"}
        with _patched_module(env), self.assertRaises(ConfigurationError) as ctx:
            validate_startup_config()
        self.assertIn("DATA_PROVIDER", str(ctx.exception))

    def test_massive_key_required_when_massive_mode(self):
        env = {
            **_VALID_SANDBOX_ENV,
            "DATA_PROVIDER": "massive",
            "MASSIVE_API_KEY": "massive-key",
        }
        with _patched_module(env):
            validate_startup_config()  # must not raise

    def test_tradier_provider_does_not_require_massive_key(self):
        env = {
            **_VALID_SANDBOX_ENV,
            "DATA_PROVIDER": "tradier",
            "MASSIVE_API_KEY": "",
        }
        with _patched_module(env):
            validate_startup_config()


class TestValidateStartupConfigLiveModeGate(unittest.TestCase):
    """live mode without LIVE_TRADING_CONFIRMED=true must be blocked."""

    def test_live_without_confirmation_raises(self):
        env = {
            **_VALID_SANDBOX_ENV,
            "TRADING_MODE": "live",
            "LIVE_TRADING_CONFIRMED": "false",
        }
        with _patched_module(env), self.assertRaises(ConfigurationError) as ctx:
            validate_startup_config()
        self.assertIn("LIVE_TRADING_CONFIRMED", str(ctx.exception))

    def test_live_without_confirmation_key_raises(self):
        env = {**_VALID_SANDBOX_ENV, "TRADING_MODE": "live"}
        # Remove LIVE_TRADING_CONFIRMED entirely
        env.pop("LIVE_TRADING_CONFIRMED", None)
        with _patched_module(env), patch.dict(os.environ, {}, clear=False):
            os.environ.pop("LIVE_TRADING_CONFIRMED", None)
            with self.assertRaises(ConfigurationError):
                validate_startup_config()

    def test_live_with_confirmation_passes(self):
        env = {
            **_VALID_SANDBOX_ENV,
            "TRADING_MODE": "live",
            "LIVE_TRADING_CONFIRMED": "true",
        }
        with _patched_module(env):
            validate_startup_config()  # must not raise

    def test_sandbox_does_not_require_live_confirmation(self):
        env = {**_VALID_SANDBOX_ENV, "TRADING_MODE": "sandbox", "LIVE_TRADING_CONFIRMED": "false"}
        with _patched_module(env):
            validate_startup_config()  # must not raise


class TestValidateStartupConfigMultipleErrors(unittest.TestCase):
    """
    All problems must be collected and reported in a single exception.
    The user should NOT need multiple restart cycles to discover each missing var.
    """

    def test_two_missing_vars_both_reported(self):
        env = {
            **_VALID_SANDBOX_ENV,
            "TRADIER_API_KEY": "",
            "TRADIER_ACCOUNT_ID": "",
        }
        with _patched_module(env), self.assertRaises(ConfigurationError) as ctx:
            validate_startup_config()
        msg = str(ctx.exception)
        self.assertIn("TRADIER_API_KEY", msg)
        self.assertIn("TRADIER_ACCOUNT_ID", msg)

    def test_three_missing_vars_all_reported(self):
        env = {
            "TRADIER_API_KEY": "",
            "TRADIER_ACCOUNT_ID": "",
            "TRADING_MODE": "sandbox",
            "TRADIER_ENVIRONMENT": "sandbox",
            "DATA_PROVIDER": "massive",
            "MASSIVE_API_KEY": "",
            "LIVE_TRADING_CONFIRMED": "false",
        }
        with _patched_module(env), self.assertRaises(ConfigurationError) as ctx:
            validate_startup_config()
        msg = str(ctx.exception)
        self.assertIn("TRADIER_API_KEY", msg)
        self.assertIn("TRADIER_ACCOUNT_ID", msg)
        self.assertIn("MASSIVE_API_KEY", msg)

    def test_error_message_mentions_problem_count(self):
        env = {
            **_VALID_SANDBOX_ENV,
            "TRADIER_API_KEY": "",
            "TRADIER_ACCOUNT_ID": "",
        }
        with _patched_module(env), self.assertRaises(ConfigurationError) as ctx:
            validate_startup_config()
        # The message should reference the count of problems
        msg = str(ctx.exception)
        self.assertIn("2", msg)

    def test_error_references_dot_env(self):
        env = {**_VALID_SANDBOX_ENV, "TRADIER_API_KEY": ""}
        with _patched_module(env), self.assertRaises(ConfigurationError) as ctx:
            validate_startup_config()
        self.assertIn(".env", str(ctx.exception))


class TestValidateConfigBackwardCompat(unittest.TestCase):
    """
    The original validate_config() return-value API must still work so
    existing callers (e.g. check_api_authentication) are unaffected.
    """

    def test_returns_tuple(self):
        with _patched_module(_VALID_SANDBOX_ENV):
            result = validate_config()
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)

    def test_returns_true_on_valid_config(self):
        with _patched_module(_VALID_SANDBOX_ENV):
            ok, msg = validate_config()
        self.assertTrue(ok)

    def test_returns_false_when_tradier_key_missing(self):
        env = {**_VALID_SANDBOX_ENV, "TRADIER_API_KEY": ""}
        with _patched_module(env):
            ok, msg = validate_config()
        self.assertFalse(ok)
        self.assertIn("TRADIER_API_KEY", msg)

    def test_error_message_is_string(self):
        env = {**_VALID_SANDBOX_ENV, "TRADIER_ACCOUNT_ID": ""}
        with _patched_module(env):
            ok, msg = validate_config()
        self.assertIsInstance(msg, str)


class TestA03StartupValidatorIntegration(unittest.TestCase):
    """
    SpyderA03_Configuration._validate_configuration() must propagate
    ConfigurationError when validate_startup_config() raises.

    The import of config.config is done *lazily* inside _validate_configuration
    to avoid triggering load_dotenv() at module-import time.  We test this by
    injecting a fake config.config module into sys.modules before calling the
    method.
    """

    def _load_a03(self):
        """Load A03 module via filesystem so sys.path quirks don't matter."""
        path = (
            _REPO_ROOT
            / "Spyder"
            / "SpyderA_Core"
            / "SpyderA03_Configuration.py"
        )
        spec = importlib.util.spec_from_file_location("_a03_t54", path)
        mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        return mod

    def test_a03_has_validate_configuration_method(self):
        """ConfigManager must expose _validate_configuration."""
        a03 = self._load_a03()
        self.assertTrue(hasattr(a03.ConfigManager, "_validate_configuration"))

    def test_a03_configmanager_is_class(self):
        a03 = self._load_a03()
        import inspect
        self.assertTrue(inspect.isclass(a03.ConfigManager))

    def test_validate_configuration_propagates_config_error(self):
        """
        If validate_startup_config() raises ConfigurationError,
        _validate_configuration() must NOT swallow it.

        We inject a fake 'config.config' module into sys.modules so the lazy
        import inside _validate_configuration picks up our mock.
        """
        a03 = self._load_a03()

        # Build a fake config.config module
        fake_config_mod = MagicMock()
        fake_cfg_err = ConfigurationError("TRADIER_API_KEY is not set")
        fake_config_mod.ConfigurationError = ConfigurationError
        fake_config_mod.validate_startup_config = MagicMock(side_effect=fake_cfg_err)

        # Build a minimal ConfigManager mock (no schema errors)
        mock_cm = MagicMock()
        mock_cm.validate.return_value = []
        mock_cm.logger = MagicMock()

        bound_method = a03.ConfigManager._validate_configuration.__get__(
            mock_cm, a03.ConfigManager
        )

        # Inject fake module so lazy import inside _validate_configuration
        # retrieves our mock instead of the real config.config
        with patch.dict(sys.modules, {"config.config": fake_config_mod}), self.assertRaises((ConfigurationError, RuntimeError)):
            bound_method()

    def test_validate_configuration_passes_when_no_errors(self):
        """When validate_startup_config does NOT raise, method completes normally."""
        a03 = self._load_a03()

        fake_config_mod = MagicMock()
        fake_config_mod.ConfigurationError = ConfigurationError
        fake_config_mod.validate_startup_config = MagicMock()  # no side_effect → passes

        mock_cm = MagicMock()
        mock_cm.validate.return_value = []
        mock_cm.logger = MagicMock()

        bound_method = a03.ConfigManager._validate_configuration.__get__(
            mock_cm, a03.ConfigManager
        )

        with patch.dict(sys.modules, {"config.config": fake_config_mod}):
            bound_method()  # must not raise

    def test_validate_configuration_graceful_when_config_not_importable(self):
        """If config.config cannot be imported, _validate_configuration continues."""
        a03 = self._load_a03()

        mock_cm = MagicMock()
        mock_cm.validate.return_value = []
        mock_cm.logger = MagicMock()

        bound_method = a03.ConfigManager._validate_configuration.__get__(
            mock_cm, a03.ConfigManager
        )

        # Remove config.config from sys.modules and block it from being imported
        original = sys.modules.pop("config.config", None)
        try:
            with patch.dict(sys.modules, {"config.config": None}):  # type: ignore[dict-item]
                # Should not raise even though import will fail
                bound_method()
        finally:
            if original is not None:
                sys.modules["config.config"] = original


class TestA03AutonomousReadinessValidation(unittest.TestCase):
    """Focused tests for autonomous readiness config validation logic."""

    def _load_a03(self):
        path = (
            _REPO_ROOT
            / "Spyder"
            / "SpyderA_Core"
            / "SpyderA03_Configuration.py"
        )
        spec = importlib.util.spec_from_file_location("_a03_t54_readiness", path)
        mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        return mod

    def _base_config(self):
        return {
            "automation": {"enabled": True},
            "autonomous_readiness": {
                "liquidity": {
                    "max_spread_pct": 0.12,
                    "max_spread_abs": 0.20,
                    "max_quote_age_ms": 1500,
                    "min_top_of_book_size": 10,
                    "min_open_interest": 500,
                    "min_volume": 50,
                    "min_oi_change_pct": -0.20,
                },
                "execution": {
                    "max_slippage_bps": 25,
                    "max_fill_latency_ms": 2500,
                    "max_partial_fill_ratio": 0.40,
                    "max_reject_rate_5m": 0.08,
                    "degrade_size_multiplier": 0.50,
                    "halt_on_quality_breach": True,
                },
                "event_clock": {
                    "enabled": True,
                    "sources": "calendar+manual",
                    "high_impact_only": True,
                    "blackout_pre_minutes": 30,
                    "blackout_post_minutes": 30,
                    "max_size_multiplier_during_event": 0.25,
                    "allowlist_strategies": [],
                },
            },
        }

    def test_paper_mode_disables_automation_on_blocking_error(self):
        a03 = self._load_a03()
        cm = a03.ConfigManager.__new__(a03.ConfigManager)

        cfg = self._base_config()
        cfg["autonomous_readiness"]["execution"]["degrade_size_multiplier"] = 0.10
        cfg["autonomous_readiness"]["event_clock"]["max_size_multiplier_during_event"] = 0.25

        result = cm.validate_autonomous_readiness_config(cfg, "paper")

        self.assertTrue(result["ok"])
        self.assertFalse(result["effective"]["automation"]["enabled"])
        self.assertGreaterEqual(len(result["errors"]), 1)
        self.assertTrue(any("automation disabled" in w for w in result["warnings"]))

    def test_live_mode_blocks_on_blocking_error(self):
        a03 = self._load_a03()
        cm = a03.ConfigManager.__new__(a03.ConfigManager)

        cfg = self._base_config()
        cfg["autonomous_readiness"]["execution"]["degrade_size_multiplier"] = 0.10
        cfg["autonomous_readiness"]["event_clock"]["max_size_multiplier_during_event"] = 0.25

        result = cm.validate_autonomous_readiness_config(cfg, "live")

        self.assertFalse(result["ok"])
        self.assertGreaterEqual(len(result["errors"]), 1)

    def test_invalid_event_source_falls_back_to_manual(self):
        a03 = self._load_a03()
        cm = a03.ConfigManager.__new__(a03.ConfigManager)

        cfg = self._base_config()
        cfg["autonomous_readiness"]["event_clock"]["sources"] = "invalid-source"

        result = cm.validate_autonomous_readiness_config(cfg, "paper")

        self.assertEqual(
            result["effective"]["autonomous_readiness"]["event_clock"]["sources"],
            "manual",
        )
        self.assertTrue(any("fallback=manual" in w for w in result["warnings"]))

    def test_env_override_applies_before_validation(self):
        a03 = self._load_a03()
        cm = a03.ConfigManager.__new__(a03.ConfigManager)

        cfg = self._base_config()
        with patch.dict(os.environ, {"SPYDER_EVENT_CLOCK_BLACKOUT_PRE_MINUTES": "45"}, clear=False):
            result = cm.validate_autonomous_readiness_config(cfg, "paper")

        self.assertEqual(
            result["effective"]["autonomous_readiness"]["event_clock"]["blackout_pre_minutes"],
            45,
        )

    def test_invalid_allowlist_items_are_removed(self):
        a03 = self._load_a03()
        cm = a03.ConfigManager.__new__(a03.ConfigManager)

        cfg = self._base_config()
        cfg["autonomous_readiness"]["event_clock"]["allowlist_strategies"] = ["D03", 7, "", None]

        result = cm.validate_autonomous_readiness_config(cfg, "paper")

        self.assertEqual(
            result["effective"]["autonomous_readiness"]["event_clock"]["allowlist_strategies"],
            ["D03"],
        )
        self.assertTrue(any("allowlist_strategies" in w for w in result["warnings"]))


class _DummyStartButton:
    """Lightweight start button test double for dashboard helper tests."""

    def __init__(self):
        self.text = ""
        self.stylesheet = ""
        self.tooltip = ""

    def setText(self, text: str) -> None:
        self.text = text

    def setStyleSheet(self, stylesheet: str) -> None:
        self.stylesheet = stylesheet

    def setToolTip(self, tooltip: str) -> None:
        self.tooltip = tooltip


class TestG05StartupReadinessHelpers(unittest.TestCase):
    """Focused tests for G05 startup readiness helper behavior."""

    def _load_g05(self):
        import types

        class _BaseQtObject:
            """Lightweight class placeholder for Qt symbols."""

            def __init__(self, *args, **kwargs):
                pass

        class _SignalStub:
            def __init__(self, *args, **kwargs):
                pass

            def connect(self, *args, **kwargs):
                return None

            def emit(self, *args, **kwargs):
                return None

        class _AnyAttrModule(types.ModuleType):
            """Module stub that resolves unknown attributes to a dummy class."""

            def __getattr__(self, name):
                val = _BaseQtObject
                setattr(self, name, val)
                return val

        class _QtNamespace:
            def __getattr__(self, name):
                return 0

        class _QApplicationStub(_BaseQtObject):
            @classmethod
            def instance(cls):
                return None

        qtw = _AnyAttrModule("PySide6.QtWidgets")
        qtc = _AnyAttrModule("PySide6.QtCore")
        qtg = _AnyAttrModule("PySide6.QtGui")

        for name in [
            "QDialog",
            "QDialogButtonBox",
            "QFrame",
            "QGridLayout",
            "QGroupBox",
            "QHBoxLayout",
            "QHeaderView",
            "QLabel",
            "QLineEdit",
            "QMainWindow",
            "QMenu",
            "QMessageBox",
            "QPushButton",
            "QScrollArea",
            "QSizePolicy",
            "QSplitter",
            "QTableWidget",
            "QTableWidgetItem",
            "QTextEdit",
            "QTreeWidget",
            "QTreeWidgetItem",
            "QVBoxLayout",
            "QWidget",
        ]:
            setattr(qtw, name, _BaseQtObject)
        qtw.QApplication = _QApplicationStub

        for name in [
            "QModelIndex",
            "QMutex",
            "QMutexLocker",
            "QObject",
            "QRect",
            "QThread",
            "QTimer",
        ]:
            setattr(qtc, name, _BaseQtObject)
        qtc.Signal = lambda *args, **kwargs: _SignalStub()
        qtc.Slot = lambda *args, **kwargs: (lambda func: func)
        qtc.Qt = _QtNamespace()

        for name in ["QBrush", "QColor", "QFont", "QPainter", "QPen", "QTextCursor"]:
            setattr(qtg, name, _BaseQtObject)

        pyside6 = _AnyAttrModule("PySide6")
        pyside6.QtWidgets = qtw
        pyside6.QtCore = qtc
        pyside6.QtGui = qtg

        module_keys = [
            "PySide6",
            "PySide6.QtWidgets",
            "PySide6.QtCore",
            "PySide6.QtGui",
            "PySide6.QtCharts",
            "PySide6.QtNetwork",
        ]
        saved_modules = {k: sys.modules[k] for k in module_keys if k in sys.modules}
        sys.modules.update(
            {
                "PySide6": pyside6,
                "PySide6.QtWidgets": qtw,
                "PySide6.QtCore": qtc,
                "PySide6.QtGui": qtg,
                "PySide6.QtCharts": types.ModuleType("PySide6.QtCharts"),
                "PySide6.QtNetwork": types.ModuleType("PySide6.QtNetwork"),
            }
        )

        path = (
            _REPO_ROOT
            / "Spyder"
            / "SpyderG_GUI"
            / "SpyderG05_TradingDashboard.py"
        )
        spec = importlib.util.spec_from_file_location("_g05_t54_readiness", path)
        mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
        try:
            spec.loader.exec_module(mod)  # type: ignore[union-attr]
        finally:
            for key in module_keys:
                if key in saved_modules:
                    sys.modules[key] = saved_modules[key]
                else:
                    sys.modules.pop(key, None)
        return mod

    def test_collect_state_marks_safe_fallback_in_paper_mode(self):
        g05 = self._load_g05()
        dashboard = g05.SpyderTradingDashboard.__new__(g05.SpyderTradingDashboard)

        fake_cfg = MagicMock()
        fake_cfg.get.side_effect = lambda key, default=None: {
            "trading.mode": "paper",
            "automation.enabled": False,
        }.get(key, default)
        fake_cfg.config_data = {}
        fake_cfg.validate_autonomous_readiness_config.return_value = {
            "warnings": ["paper mode fallback"],
            "errors": ["execution.degrade_size_multiplier out of bounds"],
        }
        fake_cfg_module = MagicMock()
        fake_cfg_module.get_config_manager.return_value = fake_cfg

        with patch.dict(
            sys.modules,
            {"Spyder.SpyderA_Core.SpyderA03_Configuration": fake_cfg_module},
            clear=False,
        ):
            state = dashboard._collect_startup_readiness_state()

        self.assertTrue(state["checked"])
        self.assertEqual(state["mode"], "paper")
        self.assertFalse(state["automation_enabled"])
        self.assertTrue(state["safe_fallback_applied"])
        self.assertFalse(state["live_blocking"])
        self.assertEqual(state["source"], "A03.ConfigManager")

    def test_emit_logs_styles_button_for_safe_mode(self):
        g05 = self._load_g05()
        dashboard = g05.SpyderTradingDashboard.__new__(g05.SpyderTradingDashboard)

        dashboard._startup_readiness_state = {
            "checked": True,
            "mode": "paper",
            "warnings": ["warn-a"],
            "errors": ["err-a"],
            "safe_fallback_applied": True,
            "live_blocking": False,
        }
        log_messages = []
        dashboard.add_system_log = lambda msg: log_messages.append(msg)
        dashboard.start_btn = _DummyStartButton()

        dashboard._emit_startup_readiness_logs()

        self.assertTrue(any("STARTUP SAFE MODE" in msg for msg in log_messages))
        self.assertEqual(dashboard.start_btn.text, "SAFE MODE (AUTO OFF)")
        self.assertIn("background-color", dashboard.start_btn.stylesheet)
        self.assertIn("automation.enabled=false", dashboard.start_btn.tooltip)

    def test_append_banner_unavailable_when_readiness_not_checked(self):
        g05 = self._load_g05()
        dashboard = g05.SpyderTradingDashboard.__new__(g05.SpyderTradingDashboard)

        dashboard.system_logs = []
        dashboard._startup_readiness_state = {
            "checked": False,
            "source": "unavailable: mock failure",
        }

        dashboard._append_startup_readiness_banner("09:30:00")

        self.assertEqual(len(dashboard.system_logs), 1)
        self.assertIn("STARTUP READINESS: unavailable", dashboard.system_logs[0])


# ==============================================================================
# MAIN
# ==============================================================================

if __name__ == "__main__":
    unittest.main(verbosity=2)
