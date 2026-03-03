#!/usr/bin/env python3
# -*- coding: utf-8 -*-
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
from typing import Iterator
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
    "DATA_PROVIDER": "databento",
    "DATABENTO_API_KEY": "db-key-xyz",
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
    orig_databento = dict(_cfg_mod.DATABENTO_CONFIG)
    orig_polygon = dict(_cfg_mod.POLYGON_CONFIG)
    orig_provider = _cfg_mod.DATA_PROVIDER

    # Apply env-driven state to module-level dicts
    _cfg_mod.TRADIER_CONFIG["api_key"] = env_overrides.get("TRADIER_API_KEY", "")
    _cfg_mod.TRADIER_CONFIG["account_id"] = env_overrides.get("TRADIER_ACCOUNT_ID", "")
    provider = env_overrides.get("DATA_PROVIDER", "databento")
    _cfg_mod.DATA_PROVIDER = provider
    _cfg_mod.DATABENTO_CONFIG["api_key"] = env_overrides.get("DATABENTO_API_KEY", "")
    _cfg_mod.POLYGON_CONFIG["api_key"] = env_overrides.get("POLYGON_API_KEY", "")

    with patch.dict(os.environ, env_overrides, clear=False):
        try:
            yield
        finally:
            _cfg_mod.TRADIER_CONFIG.update(orig_tradier)
            _cfg_mod.DATABENTO_CONFIG.update(orig_databento)
            _cfg_mod.POLYGON_CONFIG.update(orig_polygon)
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

    def test_polygon_provider_with_key(self):
        env = {
            **_VALID_SANDBOX_ENV,
            "DATA_PROVIDER": "polygon",
            "POLYGON_API_KEY": "poly-key-123",
            "DATABENTO_API_KEY": "",  # not needed when polygon
        }
        with _patched_module(env):
            validate_startup_config()


class TestValidateStartupConfigMissingTradierApiKey(unittest.TestCase):
    """Missing TRADIER_API_KEY must appear in the error."""

    def test_raises_configuration_error(self):
        env = {**_VALID_SANDBOX_ENV, "TRADIER_API_KEY": ""}
        with _patched_module(env):
            with self.assertRaises(ConfigurationError):
                validate_startup_config()

    def test_error_mentions_tradier_api_key(self):
        env = {**_VALID_SANDBOX_ENV, "TRADIER_API_KEY": ""}
        with _patched_module(env):
            with self.assertRaises(ConfigurationError) as ctx:
                validate_startup_config()
        self.assertIn("TRADIER_API_KEY", str(ctx.exception))


class TestValidateStartupConfigMissingTradierAccountId(unittest.TestCase):
    """Missing TRADIER_ACCOUNT_ID must appear in the error."""

    def test_raises_configuration_error(self):
        env = {**_VALID_SANDBOX_ENV, "TRADIER_ACCOUNT_ID": ""}
        with _patched_module(env):
            with self.assertRaises(ConfigurationError):
                validate_startup_config()

    def test_error_mentions_tradier_account_id(self):
        env = {**_VALID_SANDBOX_ENV, "TRADIER_ACCOUNT_ID": ""}
        with _patched_module(env):
            with self.assertRaises(ConfigurationError) as ctx:
                validate_startup_config()
        self.assertIn("TRADIER_ACCOUNT_ID", str(ctx.exception))


class TestValidateStartupConfigInvalidMode(unittest.TestCase):
    """Invalid TRADING_MODE must be rejected."""

    def test_empty_mode_raises(self):
        env = {**_VALID_SANDBOX_ENV, "TRADING_MODE": ""}
        with _patched_module(env):
            with self.assertRaises(ConfigurationError):
                validate_startup_config()

    def test_typo_mode_raises(self):
        env = {**_VALID_SANDBOX_ENV, "TRADING_MODE": "Live"}  # wrong case
        with _patched_module(env):
            with self.assertRaises(ConfigurationError):
                validate_startup_config()

    def test_unknown_mode_error_mentions_value(self):
        env = {**_VALID_SANDBOX_ENV, "TRADING_MODE": "production"}
        with _patched_module(env):
            with self.assertRaises(ConfigurationError) as ctx:
                validate_startup_config()
        self.assertIn("production", str(ctx.exception))

    def test_valid_modes_accepted(self):
        for mode in ("sandbox", "paper"):
            env = {**_VALID_SANDBOX_ENV, "TRADING_MODE": mode}
            with _patched_module(env):
                validate_startup_config()  # must not raise


class TestValidateStartupConfigDataProvider(unittest.TestCase):
    """Missing data-provider key must be caught."""

    def test_missing_databento_key_raises(self):
        env = {**_VALID_SANDBOX_ENV, "DATABENTO_API_KEY": "", "DATA_PROVIDER": "databento"}
        with _patched_module(env):
            with self.assertRaises(ConfigurationError) as ctx:
                validate_startup_config()
        self.assertIn("DATABENTO_API_KEY", str(ctx.exception))

    def test_missing_polygon_key_raises(self):
        env = {
            **_VALID_SANDBOX_ENV,
            "DATA_PROVIDER": "polygon",
            "POLYGON_API_KEY": "",
            "DATABENTO_API_KEY": "irrelevant",
        }
        with _patched_module(env):
            with self.assertRaises(ConfigurationError) as ctx:
                validate_startup_config()
        self.assertIn("POLYGON_API_KEY", str(ctx.exception))

    def test_invalid_provider_name_raises(self):
        env = {**_VALID_SANDBOX_ENV, "DATA_PROVIDER": "quandl"}
        with _patched_module(env):
            with self.assertRaises(ConfigurationError) as ctx:
                validate_startup_config()
        self.assertIn("DATA_PROVIDER", str(ctx.exception))

    def test_databento_key_not_required_for_polygon_mode(self):
        env = {
            **_VALID_SANDBOX_ENV,
            "DATA_PROVIDER": "polygon",
            "POLYGON_API_KEY": "poly-key",
            "DATABENTO_API_KEY": "",
        }
        with _patched_module(env):
            validate_startup_config()  # must not raise

    def test_polygon_key_not_required_for_databento_mode(self):
        env = {
            **_VALID_SANDBOX_ENV,
            "DATA_PROVIDER": "databento",
            "DATABENTO_API_KEY": "db-key",
            "POLYGON_API_KEY": "",
        }
        with _patched_module(env):
            validate_startup_config()  # must not raise


class TestValidateStartupConfigLiveModeGate(unittest.TestCase):
    """live mode without LIVE_TRADING_CONFIRMED=true must be blocked."""

    def test_live_without_confirmation_raises(self):
        env = {
            **_VALID_SANDBOX_ENV,
            "TRADING_MODE": "live",
            "LIVE_TRADING_CONFIRMED": "false",
        }
        with _patched_module(env):
            with self.assertRaises(ConfigurationError) as ctx:
                validate_startup_config()
        self.assertIn("LIVE_TRADING_CONFIRMED", str(ctx.exception))

    def test_live_without_confirmation_key_raises(self):
        env = {**_VALID_SANDBOX_ENV, "TRADING_MODE": "live"}
        # Remove LIVE_TRADING_CONFIRMED entirely
        env.pop("LIVE_TRADING_CONFIRMED", None)
        with _patched_module(env):
            with patch.dict(os.environ, {}, clear=False):
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
        with _patched_module(env):
            with self.assertRaises(ConfigurationError) as ctx:
                validate_startup_config()
        msg = str(ctx.exception)
        self.assertIn("TRADIER_API_KEY", msg)
        self.assertIn("TRADIER_ACCOUNT_ID", msg)

    def test_three_missing_vars_all_reported(self):
        env = {
            "TRADIER_API_KEY": "",
            "TRADIER_ACCOUNT_ID": "",
            "TRADING_MODE": "sandbox",
            "DATA_PROVIDER": "databento",
            "DATABENTO_API_KEY": "",
            "LIVE_TRADING_CONFIRMED": "false",
        }
        with _patched_module(env):
            with self.assertRaises(ConfigurationError) as ctx:
                validate_startup_config()
        msg = str(ctx.exception)
        self.assertIn("TRADIER_API_KEY", msg)
        self.assertIn("TRADIER_ACCOUNT_ID", msg)
        self.assertIn("DATABENTO_API_KEY", msg)

    def test_error_message_mentions_problem_count(self):
        env = {
            **_VALID_SANDBOX_ENV,
            "TRADIER_API_KEY": "",
            "TRADIER_ACCOUNT_ID": "",
        }
        with _patched_module(env):
            with self.assertRaises(ConfigurationError) as ctx:
                validate_startup_config()
        # The message should reference the count of problems
        msg = str(ctx.exception)
        self.assertIn("2", msg)

    def test_error_references_dot_env(self):
        env = {**_VALID_SANDBOX_ENV, "TRADIER_API_KEY": ""}
        with _patched_module(env):
            with self.assertRaises(ConfigurationError) as ctx:
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
        with patch.dict(sys.modules, {"config.config": fake_config_mod}):
            with self.assertRaises((ConfigurationError, RuntimeError)):
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


# ==============================================================================
# MAIN
# ==============================================================================

if __name__ == "__main__":
    unittest.main(verbosity=2)
