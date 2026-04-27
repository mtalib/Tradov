#!/usr/bin/env python3
"""Focused coverage tests for Q03, Q08, and Q09 validator scripts."""

from __future__ import annotations

import importlib
import json
import os
import runpy
import sys
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

import pytest

from Spyder.SpyderQ_Scripts import SpyderQ03_ValidateConfiguration as q03
from Spyder.SpyderQ_Scripts import SpyderQ08_ValidatePackageExports as q08
from Spyder.SpyderQ_Scripts import SpyderQ09_ValidateMissingExports as q09


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def test_q03_validation_result_string_formatting():
    result = q03.ValidationResult(
        key="FOO",
        level=q03.ValidationLevel.ERROR,
        message="broken",
        suggestion="fix it",
    )
    text = str(result)
    assert "[ERROR] FOO: broken" in text
    assert "fix it" in text


def test_q03_add_result_routes_by_level():
    validator = q03.ConfigurationValidator()
    validator.add_result(q03.ValidationResult("A", q03.ValidationLevel.ERROR, "e"))
    validator.add_result(q03.ValidationResult("B", q03.ValidationLevel.WARNING, "w"))
    validator.add_result(q03.ValidationResult("C", q03.ValidationLevel.INFO, "i"))

    assert [r.key for r in validator.errors] == ["A"]
    assert [r.key for r in validator.warnings] == ["B"]
    assert [r.key for r in validator.info] == ["C"]


def test_q03_validate_all_safe_mode(monkeypatch):
    env = {
        "TRADING_MODE": "paper",
        "TRADIER_API_KEY": "x" * 24,
        "TRADIER_ACCOUNT_ID": "ABC123",
        "MASSIVE_API_KEY": "x" * 16,
        "MAX_POSITION_SIZE": "0.10",
        "MAX_DAILY_LOSS": "0.05",
        "MAX_OPEN_POSITIONS": "5",
        "LOG_LEVEL": "INFO",
        "GUI_LOG_LEVEL": "INFO",
        "LOG_FILE_PATH": "logs/spyder.log",
        "EMERGENCY_OVERRIDE_PASSWORD": "very-secure-password",
    }
    for key, value in env.items():
        monkeypatch.setenv(key, value)

    validator = q03.ConfigurationValidator()
    buf = StringIO()
    with redirect_stdout(buf):
        is_valid = validator.validate_all()

    assert is_valid is True
    out = buf.getvalue()
    assert "CONFIGURATION VALID" in out
    assert len(validator.errors) == 0


def test_q03_live_mode_and_invalid_numeric_values(monkeypatch):
    env = {
        "TRADING_MODE": "live",
        "LIVE_TRADING_CONFIRMED": "false",
        "TRADIER_API_KEY": "short",
        "TRADIER_ACCOUNT_ID": "your_account_id_here",
        "MASSIVE_API_KEY": "short",
        "MAX_POSITION_SIZE": "2.0",
        "MAX_DAILY_LOSS": "oops",
        "MAX_OPEN_POSITIONS": "0",
        "LOG_LEVEL": "BAD",
        "GUI_LOG_LEVEL": "BAD",
        "EMERGENCY_OVERRIDE_PASSWORD": "short",
    }
    for key, value in env.items():
        monkeypatch.setenv(key, value)

    validator = q03.ConfigurationValidator()
    validator._validate_trading_mode()
    validator._validate_tradier_config()
    validator._validate_massive_config()
    validator._validate_risk_config()
    validator._validate_logging_config()
    validator._validate_security_config()

    error_keys = {r.key for r in validator.errors}
    warning_keys = {r.key for r in validator.warnings}

    assert "LIVE_TRADING_CONFIRMED" in error_keys
    assert "MAX_POSITION_SIZE" in error_keys
    assert "MAX_DAILY_LOSS" in error_keys
    assert "MAX_OPEN_POSITIONS" in error_keys
    assert "TRADIER_ACCOUNT_ID" in error_keys
    assert "LOG_LEVEL" in warning_keys
    assert "GUI_LOG_LEVEL" in warning_keys
    assert "EMERGENCY_OVERRIDE_PASSWORD" in warning_keys


def test_q03_main_without_env_file(monkeypatch):
    script_path = Path(q03.__file__)
    monkeypatch.setattr(q03.Path, "exists", lambda self: False if self == Path(q03.project_root) / ".env" else Path.exists(self))

    captured = StringIO()
    monkeypatch.setattr(q03.ConfigurationValidator, "validate_all", lambda self: True)
    with redirect_stdout(captured), pytest.raises(SystemExit) as exc:
        q03.main()

    assert exc.value.code == 0
    assert "No .env file found" in captured.getvalue()
    assert str(script_path)


def test_q08_validate_package_ok_failures_and_no_all(tmp_path, monkeypatch):
    class _PkgOk:
        __all__ = ["A"]
        A = object()

    class _PkgFail:
        __all__ = ["MissingThing"]

    class _PkgNoAll:
        x = 1

    def _import_module(name: str):
        if name == "Spyder.PkgOk":
            return _PkgOk
        if name == "Spyder.PkgFail":
            return _PkgFail
        if name == "Spyder.PkgNoAll":
            return _PkgNoAll
        raise ModuleNotFoundError(name)

    monkeypatch.setattr(q08.importlib, "import_module", _import_module)

    ok = q08.validate_package("Spyder.PkgOk")
    fail = q08.validate_package("Spyder.PkgFail")
    no_all = q08.validate_package("Spyder.PkgNoAll")

    assert ok["status"] == "ok"
    assert ok["passed"] == ["A"]
    assert fail["status"] == "failures"
    assert fail["failed"][0]["symbol"] == "MissingThing"
    assert no_all["status"] == "no_all"


def test_q08_validate_package_import_error(tmp_path, monkeypatch):
    def _import_module(_name: str):
        raise RuntimeError("boom")

    monkeypatch.setattr(q08.importlib, "import_module", _import_module)

    result = q08.validate_package("Spyder.PkgBoom")
    assert result["status"] == "import_error"
    assert "RuntimeError" in result["error"]


def test_q08_resolve_packages_and_main_json(monkeypatch):
    args = type("Args", (), {"package": "SpyderE_Risk"})
    assert q08._resolve_packages(args) == ["Spyder.SpyderE_Risk"]

    monkeypatch.setattr(q08, "validate_package", lambda pkg: {"package": pkg, "status": "ok", "error": None, "all_count": 1, "passed": ["x"], "failed": []})
    buf = StringIO()
    with redirect_stdout(buf):
        rc = q08.main(["--package", "SpyderE_Risk", "--json"])
    assert rc == 0
    data = json.loads(buf.getvalue())
    assert data[0]["package"] == "Spyder.SpyderE_Risk"


def test_q08_main_failure_and_no_exit_code(monkeypatch):
    monkeypatch.setattr(q08, "validate_package", lambda pkg: {"package": pkg, "status": "failures", "error": None, "all_count": 1, "passed": [], "failed": [{"symbol": "x", "reason": "bad"}]})
    assert q08.main(["--package", "SpyderE_Risk"]) == 1
    assert q08.main(["--package", "SpyderE_Risk", "--no-exit-code"]) == 0


def test_q09_find_modules_and_references(tmp_path):
    pkg = tmp_path / "SpyderA_Core"
    _write(pkg / "__init__.py", "from .SpyderA01_Main import Main\nNAME='SpyderA02_Helper'\n")
    _write(pkg / "SpyderA01_Main.py", "class Main: pass\n")
    _write(pkg / "SpyderA02_Helper.py", "def helper(): pass\n")
    _write(pkg / "test_ignore.py", "x=1\n")

    modules = q09._find_module_files(pkg)
    refs = q09._init_references(pkg / "__init__.py")

    assert modules == ["SpyderA01_Main", "SpyderA02_Helper"]
    assert "SpyderA01_Main" in refs
    assert "SpyderA02_Helper" in refs


def test_q09_validate_package_detects_missing(tmp_path):
    pkg = tmp_path / "SpyderB_Broker"
    _write(pkg / "__init__.py", "from .SpyderB01_Main import Main\n")
    _write(pkg / "SpyderB01_Main.py", "class Main: pass\n")
    _write(pkg / "SpyderB02_Missing.py", "x = 1\n")

    result = q09.validate_package(pkg)
    assert result.package_name == "SpyderB_Broker"
    assert result.total_modules == 2
    assert result.missing_modules == ["SpyderB02_Missing"]


def test_q09_run_validation_json_and_package_not_found(tmp_path):
    root = tmp_path / "Spyder"
    _write(root / "SpyderC_MarketData" / "__init__.py", "from .SpyderC01_Data import Data\n")
    _write(root / "SpyderC_MarketData" / "SpyderC01_Data.py", "class Data: pass\n")

    buf = StringIO()
    with redirect_stdout(buf):
        rc = q09.run_validation(root=root, as_json=True)
    assert rc == 0
    data = json.loads(buf.getvalue())
    assert data["packages_with_missing"] == 0

    buf = StringIO()
    with redirect_stdout(buf):
        rc = q09.run_validation(root=root, single_package="SpyderX_Agents", as_json=True)
    assert rc == 1
    assert "error" in json.loads(buf.getvalue())


def test_q09_main_with_root_argument(tmp_path, monkeypatch):
    root = tmp_path / "Spyder"
    _write(root / "SpyderD_Strategies" / "__init__.py", "")
    _write(root / "SpyderD_Strategies" / "SpyderD01_Main.py", "x=1\n")

    old_argv = sys.argv[:]
    sys.argv = ["prog", "--root", str(root), "--summary"]
    try:
        rc = q09.main()
    finally:
        sys.argv = old_argv

    assert rc == 1
